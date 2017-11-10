from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django import forms
from formtools.wizard.views import SessionWizardView, StepsHelper
from formtools.wizard.storage import get_storage

import pandas as pd
import math
from celery import chord

from core.models import (Profile, Project, ProjectPermissions, Model, Data, Label,
                         DataLabel, DataPrediction, Queue, DataQueue, AssignedData,
                         TrainingSet)
from core.forms import (ProjectUpdateForm, PermissionsFormSet, LabelFormSet,
                        ProjectWizardForm, DataWizardForm)
from core.serializers import DataSerializer
from core.templatetags import project_extras
import core.util as util
from core import tasks


# Projects
class ProjectCode(LoginRequiredMixin, TemplateView):
    template_name = 'smart/smart.html'

    def get_context_data(self, **kwargs):
        ctx = super(ProjectCode, self).get_context_data(**kwargs)

        ctx['pk'] = self.kwargs['pk']

        return ctx


class ProjectList(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/list.html'
    paginate_by = 10
    ordering = 'name'

    def get_queryset(self):
        # Projects profile created
        qs1 = Project.objects.filter(creator=self.request.user.profile)

        # Projects profile has permissions for
        qs2 = Project.objects.filter(projectpermissions__profile=self.request.user.profile)

        qs = qs1 | qs2

        return qs.distinct().order_by(self.ordering)


class ProjectDetail(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/detail.html'

    def get_object(self, *args, **kwargs):
        obj = super(ProjectDetail, self).get_object(*args, **kwargs)

        # Check profile permissions before showing project detail page
        if project_extras.proj_permission_level(obj, self.request.user.profile) == 0:
            raise PermissionDenied('You do not have permission to view this project')
        return obj


def upload_data(form_data, project, queue=None):
    """Perform data upload given validated form_data.

    1. Add data to database
    2. If new project then fill queue (only new project will pass queue object)
    3. Save the uploaded data file
    4. Create tf_idf file
    5. Check and Trigger model
    """
    data_objs = util.add_data(project, form_data)
    if queue:
        util.fill_queue(queue, orderby='random')
    util.save_data_file(form_data, project.pk)

    # Since User can upload Labeled Data and this data is added to current training_set
    # we need to check_and_trigger model.  However since training model requires
    # tf_idf to be created we must create a chord which garuntees that tfidf
    # creation task is completed before check and trigger model task
    chord(
          tasks.send_tfidf_creation_task.s(DataSerializer(data_objs, many=True).data, project.pk),
          tasks.send_check_and_trigger_model_task.si(project.pk)
    ).apply_async()


class ProjectCreateWizard(LoginRequiredMixin, SessionWizardView):
    file_storage = FileSystemStorage(location=settings.DATA_DIR)
    form_list = [
        ('project', ProjectWizardForm),
        ('labels', LabelFormSet),
        ('permissions', PermissionsFormSet),
        ('data', DataWizardForm)
    ]

    def get_template_names(self):
        return 'projects/create_wizard.html'

    def get_form_kwargs(self, step):
        kwargs = {}
        if step == 'data':
            temp = []
            for label in self.get_cleaned_data_for_step('labels'):
                temp.append(label['name'])
            kwargs['labels'] = temp
        return kwargs

    def get_form_kwargs_special(self, step=None):
        form_kwargs = {}

        if step == 'permissions':
            form_kwargs.update({
                'action': 'create',
                'profile': self.request.user.profile
            })

        return form_kwargs

    def get_form_prefix(self, step=None, form=None):
        prefix = ''

        if step == 'labels':
            prefix = 'label_set'
        if step == 'permissions':
            prefix = 'permission_set'

        return prefix

    def get_form(self, step=None, data=None, files=None):
        """
        Overriding get_form.  All the code is exactly the same except the if
        statement by the return.  InlineLabelFormsets do not allow kwargs to be
        added to them through the traditional method of adding the kwargs to
        their init method.  Instead they must be passed using the `form_kwargs`
        parameter.  So If the step is a inline formset pass those special kwargs
        """
        if step is None:
            step = self.steps.current
        form_class = self.form_list[step]
        # prepare the kwargs for the form instance.
        kwargs = self.get_form_kwargs(step)
        kwargs.update({
            'data': data,
            'files': files,
            'prefix': self.get_form_prefix(step, form_class),
            'initial': self.get_form_initial(step),
        })
        if issubclass(form_class, (forms.ModelForm, forms.models.BaseInlineFormSet)):
            # If the form is based on ModelForm or InlineFormSet,
            # add instance if available and not previously set.
            kwargs.setdefault('instance', self.get_form_instance(step))
        elif issubclass(form_class, forms.models.BaseModelFormSet):
            # If the form is based on ModelFormSet, add queryset if available
            # and not previous set.
            kwargs.setdefault('queryset', self.get_form_instance(step))

        if step == 'labels' or step == 'permissions':
            return form_class(**kwargs, form_kwargs=self.get_form_kwargs_special(step))
        else:
            return form_class(**kwargs)

    def done(self, form_list, form_dict, **kwargs):
        proj = form_dict['project']
        labels = form_dict['labels']
        permissions = form_dict['permissions']
        data = form_dict['data']

        with transaction.atomic():
            # Project
            proj_obj = proj.save(commit=False)
            proj_obj.creator = self.request.user.profile
            proj_obj.save()

            # Training Set
            training_set = TrainingSet.objects.create(project=proj_obj, set_number=0)

            # Labels
            labels.instance = proj_obj
            labels.save()

            # Permissions
            permissions.instance = proj_obj
            permissions.save()

            # Queue
            batch_size = 10 * len([x for x in labels if x.cleaned_data != {} and x.cleaned_data['DELETE'] != True])
            num_coders = len([x for x in permissions if x.cleaned_data != {} and x.cleaned_data['DELETE'] != True]) + 1
            q_length = util.find_queue_length(batch_size, num_coders)

            queue = util.add_queue(project=proj_obj, length=q_length)

            # Data
            f_data = data.cleaned_data['data']
            upload_data(f_data, proj_obj, queue)

        return HttpResponseRedirect(proj_obj.get_absolute_url())


class ProjectUpdate(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectUpdateForm
    template_name = 'projects/update.html'

    def get_object(self, *args, **kwargs):
        obj = super(ProjectUpdate, self).get_object(*args, **kwargs)

        # Check profile permissions before showing project update page
        if project_extras.proj_permission_level(obj, self.request.user.profile) == 0:
            raise PermissionDenied('You do not have permission to view this project')
        return obj

    def get_form_kwargs(self):
        form_kwargs = super(ProjectUpdate, self).get_form_kwargs()

        form_kwargs['labels'] = list(Label.objects.filter(project=form_kwargs['instance']).values_list('name', flat=True))

        return form_kwargs

    def get_context_data(self, **kwargs):
        data = super(ProjectUpdate, self).get_context_data(**kwargs)
        if self.request.POST:
            data['permissions'] = PermissionsFormSet(self.request.POST, instance=data['project'], prefix='permissions_set', form_kwargs={'action': 'update', 'creator':data['project'].creator, 'profile': self.request.user.profile})
        else:
            data['num_data'] = Data.objects.filter(project=data['project']).count()
            data['permissions'] = PermissionsFormSet(instance=data['project'], prefix='permissions_set', form_kwargs={'action': 'update', 'creator':data['project'].creator, 'profile': self.request.user.profile})
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        permissions = context['permissions']
        with transaction.atomic():
            if permissions.is_valid():
                self.object = form.save()
                permissions.instance = self.object
                for deleted_permissions in permissions.deleted_forms:
                    del_perm_profile = deleted_permissions.cleaned_data.get('profile', None)
                    util.batch_unassign(del_perm_profile)
                permissions.save()

                # Data
                f_data = form.cleaned_data.get('data', False)
                if isinstance(f_data, pd.DataFrame):
                    upload_data(f_data, self.object)
                return redirect(self.get_success_url())
            else:
                return self.render_to_response(context)


class ProjectDelete(LoginRequiredMixin, DeleteView):
    model = Project
    template_name = 'projects/confirm_delete.html'
    success_url = reverse_lazy('projects:project_list')

    def get_object(self, *args, **kwargs):
        obj = super(ProjectDelete, self).get_object(*args, **kwargs)

        # Check profile permissions before showing project delete page
        if project_extras.proj_permission_level(obj, self.request.user.profile) == 0:
            raise PermissionDenied('You do not have permission to view this project')
        return obj