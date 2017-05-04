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

    //show revert button for any revision except current version.
    if (this.selectedIndex > 0)
        $('#span_revert_revision').show();
    else
        $('#span_revert_revision').hide();

});

function loadRevisionHistory(revisionUrl) {
    var currentObject,
        currentObjectText;

    $.getJSON({
        url: revisionUrl,
        success: function (data) {
            $.each(data, function(key, value) {
                currentObject = $('.history-field-container').find('.' + key);
                if (currentObject.length && value != null) {
                    currentObjectText = getComparableText(currentObject);
                    value = $($.parseHTML(value)).text().trim();
                    showDiffCourseDetails(value, currentObjectText, currentObject.siblings('.show-diff'));
                    currentObject.hide();
                }
            });
        }
    });
}

$(document).on('click', '#id_revert_revision', function (e) {
    e.preventDefault();
    $('#confirmationModal').show();
});

$(document).on('click', '#id_confirm_revert_revision', function (e) {
    // after the confirmation update the course according to the history id
    e.preventDefault();
    var revertUrl = $('select#id_select_revisions option:selected').data('revertUrl');
    $('#confirmationModal').show();
    $.ajax({
        type: "PUT",
        url: revertUrl,
        success: function (response) {
            location.reload();
        },
        error: function () {
            $('#RevertRevisionAlert').show();
        }
    });
});
