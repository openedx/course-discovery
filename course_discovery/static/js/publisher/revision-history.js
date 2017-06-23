$(document).on('change', '#id_select_revisions', function (e) {
    var revisionUrl = $(this).find(':selected').data('revisionUrl');
    // on changing the revision from drop-down set the href of button.
    $('#id_open_revision').prop("href", this.value);

    var btn_edit = $('#btn_course_edit');
    var current_btn_edit_url = btn_edit.attr('href');
    var btn_accept_revision = $('#btn_accept_revision');

    if (revisionUrl) {
        loadRevisionHistory(revisionUrl);
    } else {
        $('.show-diff').hide();
        $('.current').show();
    }

    //show revert button for any revision except current version.
    if (this.selectedIndex > 0) {
        $('#span_revert_revision').show();
        btn_edit.prop("href", $(this).find(':selected').data('revisionId'));
        var reversionValue = $('select#id_select_revisions option:selected').data('reversionValue');

        //show accept-all button.
        if (reversionValue === parseInt(btn_accept_revision.data('most-recent-revision-id'))){
            btn_accept_revision.show();
        }
        else
            btn_accept_revision.hide();
    }
    else {
        $('#span_revert_revision').hide();
        btn_edit.prop("href", current_btn_edit_url.split('?history')[0]);
        btn_accept_revision.hide();
    }

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
                    value = decodeEntities(value.split('<br>').join('<br />').trim());
                    currentObjectText = decodeEntities(currentObjectText.split('<br>').join('<br />').trim());
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


$(document).on('click', '#btn_accept_revision', function (e) {
    // after the confirmation update the course according to the history id
    e.preventDefault();
    var acceptRevisionUrl = $('select#id_select_revisions option:selected').data('acceptRevision');
//    $('#confirmationModal').show();
    $.ajax({
        type: "post",
        url: acceptRevisionUrl,
        success: function (response) {
            location.reload();
        },
        error: function () {
            $('#AcceptAllAlert').show();
        }
    });
});
