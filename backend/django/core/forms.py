from django import forms
from django.core.exceptions import ValidationError
from .models import Project, ProjectPermissions, Label
import pandas as pd
from pandas.errors import EmptyDataError, ParserError

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']

    name = forms.CharField()
    description = forms.CharField(required=False)
    data = forms.FileField()

    def clean_data(self):
        allowed_types = [
            'text/csv',
            'text/tab-separated-values'
        ]

        max_file_size = 4 * 1000 * 1000 * 1000

        data = self.cleaned_data.get('data', False)

        if data:            
            if data.size > max_file_size:
                raise ValidationError("File is too large")

            if data.content_type not in allowed_types:
                raise ValidationError("File type is not supported")

            try:
                if data.content_type == 'text/tab-separated-values':
                    data = pd.read_csv(data, header=None, sep='\t')
                elif data.content_type == 'text/csv':
                    data = pd.read_csv(data, header=None)
                else:
                    raise ValidationError("File type is not supported")

                if len(data.columns) > 1:
                    raise ValidationError("File should only contain one column")

                if len(data) < 1:
                    raise ValidationError("File should contain some data")
            except EmptyDataError:
                # For some reason when you upload data but leave other required form
                # fields blank EmptyDataError is thrown.  I can not seem to figure
                # out why it is thrown.
                pass
            except ParserError:
                # If there was an error while parsing then raise invalid file error
                raise ValidationError("Invalid file, unable to parse the file")

        return data

class ProjectUpdateForm(ProjectForm):
    data = forms.FileField(required=False)

class LabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = '__all__'

    name = forms.CharField()

class ProjectPermissionsForm(forms.ModelForm):
    class Meta:
        model = ProjectPermissions
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile', None)
        self.action = kwargs.pop('action', None)
        self.creator = kwargs.pop('creator', None)
        super(ProjectPermissionsForm, self).__init__(*args, **kwargs)

    def clean_profile(self):
        profile = self.cleaned_data.get('profile', False)
        if self.action == 'create' and profile == self.profile:
            raise ValidationError("You are the creator by default, please do not assign yourself any permissions")
        if self.action == 'update' and profile == self.creator and self.profile != self.creator:
            raise ValidationError("{0} is the creator, please do not assign them any permissions".format(self.creator))
        if self.action == 'update' and profile == self.creator and self.profile == self.creator:
            raise ValidationError("You are the creator by default, please do not assign yourself any permissions")

        return profile


LabelFormSet = forms.inlineformset_factory(Project, Label, form=LabelForm, min_num=2, validate_min=True, extra=0, can_delete=True)
PermissionsFormSet = forms.inlineformset_factory(Project, ProjectPermissions, form=ProjectPermissionsForm, extra=1, can_delete=True)


class ProjectWizardForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']


class DataWizardForm(forms.Form):
    data = forms.FileField()

    def __init__(self, *args, **kwargs):
        self.supplied_labels = kwargs.pop('labels', None)
        super(DataWizardForm, self).__init__(*args, **kwargs)

    def clean_data(self):
        allowed_types = [
            'text/csv',
            'text/tab-separated-values'
        ]
        allowed_header = ['Text', 'Label']

        max_file_size = 4 * 1000 * 1000 * 1000

        data = self.cleaned_data.get('data', False)

        if data:
            if data.size > max_file_size:
                raise ValidationError("File is too large.  Received {0} but max size is {1}."\
                                      .format(data.size, max_file_size))

            if data.content_type not in allowed_types:
                raise ValidationError("File type is not supported.  Received {0} but only {1} are supported."\
                                      .format(data.content_type, ', '.join(allowed_types)))

            try:
                if data.content_type == 'text/tab-separated-values':
                    data = pd.read_csv(data, sep='\t')
                elif data.content_type == 'text/csv':
                    data = pd.read_csv(data)
                else:
                    raise ValidationError("Unable to read file.  Please ensure it passes all the requirments")

                if data.columns.tolist() != allowed_header:
                    raise ValidationError("File headers are incorrect.  Received {0} but header must be {1}."\
                                          .format(', '.join(data.columns), ', '.join(allowed_header)))

                if len(data.columns) != len(allowed_header):
                    raise ValidationError("File has incorrect number of columns.  Received {0} but expected {1}."\
                                          .format(data.columns, len(allowed_header)))

                if len(data) < 1:
                    raise ValidationError("File should contain some data.")


                labels_in_data = data['Label'].dropna(inplace=False).unique()
                print(labels_in_data)
                print(self.supplied_labels)
                if len(labels_in_data) > 0 and set(labels_in_data) != set(self.supplied_labels):
                    raise ValidationError(
                        "Labels in file do not match labels created in step 2.  File supplied {0} "
                        "but step 2 was given {1}".format(', '.join(labels_in_data), ', '.join(self.supplied_labels))
                    )

                num_unlabeled_data = len(data[pd.isnull(data['Label'])])
                if num_unlabeled_data < 1:
                    raise ValidationError(
                        "All text in the file already has a label.  SMART needs unlabeled data "
                        "to do active learning.  Please upload a file that has less labels."
                    )
            except ParserError:
                # If there was an error while parsing then raise invalid file error
                raise ValidationError("Unable to read file.  Please ensure it passes all the requirments")

        return data
