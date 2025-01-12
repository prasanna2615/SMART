import React, { useState } from "react";

import ConfirmationModal from "./ConfirmationModal";
import { AsyncPaginate } from 'react-select-async-paginate';


const DataCardSelectLabel = ({ cardData, fn, category, includeModal }) => {
    const [selectedLabelID, setSelectedLabelID] = useState(null);
    async function loadOptions(searchString, loadedOptions, { page }) {
        const cleanCat = category || "";
        const response = await fetch(
            `/api/search_labels/${window.PROJECT_ID}/?${new URLSearchParams({ searchString, page, category: cleanCat }).toString()}`
        );
        const labels = await response.json();

        let hasMore = true;
        if (labels.next == null){
            hasMore = false;
        }
        const labelsOptions = labels ? labels.results.map(label => ({
            value: label["pk"],
            dropdownLabel: `${label["name"]} ${label["description"] !== '' ? '(' + label["description"] + ')' : ''}`
        })) : [];
      
        return {
            options: labelsOptions,
            hasMore: hasMore,
            additional: {
                page: page + 1,
            },
        };
    }



    return (
        <div className="label-select-wrapper">
            <AsyncPaginate
                key={category}
                placeholder="Select label..."
                value=""
                className="rounded"
                loadOptions={loadOptions}
                getOptionValue={(option) => option.value}
                getOptionLabel={(option) => option.dropdownLabel}
                isSearchable={true}
                onChange={(value) => {
                    if (includeModal) setSelectedLabelID(value.value);
                    else fn({ ...cardData, selectedLabelID: value.value });
                }}
                additional={{
                    page: 1,
                }}
            />
            <ConfirmationModal 
                showModal={selectedLabelID !== null}
                setSelectedLabelID={setSelectedLabelID}
                fn={ () => {
                    fn({ ...cardData, selectedLabelID });
                }}
            />
        </div>
        
    );
};

export default DataCardSelectLabel;
