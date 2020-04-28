function updateSelect2Data(el){
    var i, j,
        visibleTitlesLength,
        selectOptionsLength,
        visibleTitles = [],
        selectOptions = [],
        items = [],
        selectOptionsElement = $(el).find('.select2-hidden-accessible'),
        selectChoicesElement = $(el).find('.select2-selection__choice'),
        selectOptionElement = $(selectOptionsElement).find('option');

    selectChoicesElement.each(function(index, value){
        if (value.title){
            visibleTitles.push(value.title);
        }
    });

    selectOptionElement.each(function(index, value){
        selectOptions.push({id: value.value, text: value.text});
    });

    // Update select2 options with new data
    visibleTitlesLength = visibleTitles.length;
    selectOptionsLength = selectOptions.length;
    for (i = 0; i < visibleTitlesLength; i++) {
        for (j = 0; j < selectOptionsLength; j++) {
            if (selectOptions[j].text === visibleTitles[i]){
                items.push('<option selected="selected" value="' + selectOptions[j].id + '">' +
                           selectOptions[j].text + '</option>'
                );
            }
        }
    }

    if (items){
        selectOptionsElement.html(items.join('\n'));
    }
}

window.addEventListener('load', function(){
    $(function() {
        $('.sortable-select').parents('.form-row').each(function(index, el){
            $(el).find('ul.select2-selection__rendered').sortable({
                containment: 'parent',
                update: function(){updateSelect2Data(el);}
            })
        })
    })
});
