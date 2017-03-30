$(document).on('change', '#id_select_revisions', function (e) {
    var revisionUrl = $(this.selectedOptions).data('revisionUrl');
    // on changing the revision from dropdown set the href of button.
    $('#id_open_revision').prop("href", this.value);

    if (revisionUrl) {
        loadRevisionHistory(revisionUrl);
    } else {
        $('.show-diff').hide();
        $('.current').show();
    }
});

function loadRevisionHistory(revisionUrl) {

    $.getJSON({
        url: revisionUrl,
        success: function (data) {
            $.each(data, function(key, value) {
              var currentObject = $('.history-field-container').find('.' + key);
                if (currentObject.length && value != null) {
                    showDiffCourseDetails(value, currentObject.text(), currentObject.siblings('.show-diff'));
                    currentObject.hide();
                }
            });
        }
    });
}
