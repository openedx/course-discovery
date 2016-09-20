function updateSelect2Data(visibleCourseTitles){
    var i, j,
        visibleCourseTitlesLength,
        selectOptionsLength,
        visibleCourseTitles = [],
        selectOptions = [],
        items = [],
        selectOptionsSelector = '.field-courses .select2-hidden-accessible';

    $('.field-courses .select2-selection__choice').each(function(index, value){
        if (value.title){
            visibleCourseTitles.push(value.title);
        }
    });

    $('.field-courses .select2-hidden-accessible option').each(function(index, value){
        selectOptions.push({id: value.value, text: value.text});
    });

    // Update select2 options with new data
    visibleCourseTitlesLength = visibleCourseTitles.length;
    selectOptionsLength = selectOptions.length;
    for (i = 0; i < visibleCourseTitlesLength; i++) {
        for (j = 0; j < selectOptionsLength; j++) {
            if (selectOptions[j].text === visibleCourseTitles[i]){
                items.push('<option selected="selected" value="' + selectOptions[j].id + '">' +
                           selectOptions[j].text + '</option>'
                );
            }
        }
    }
    if (items){
        $(selectOptionsSelector).html(items.join('\n'));
    }
}
$(window).load(function(){
    $(function() {
        var domSelector = '.field-courses .select2-selection--multiple';
        $('.field-courses ul.select2-selection__rendered').sortable({
            containment: 'parent',
            update: updateSelect2Data
        })
    })
});
