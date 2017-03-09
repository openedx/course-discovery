$(document).on('click', '.btn-add-comment', function (e) {
    e.preventDefault();

    var frm_comment = $(this).closest("#frm_comment"),
    comment_box = frm_comment.find("#id_comment");

    if (!comment_box.val()) {
        comment_box.addClass('has-error');
        comment_box.focus();
    }
    else {
        $(frm_comment).submit();
    }
});

$(document).on('click', '.comment-edit', function (e) {
    e.preventDefault();
    var parentDt = this.closest('dt'),
        editableControlsHtml = '<div class="edit-controls"><button class="btn-brand btn-small comment-save">Save</button>' +
            '<button class="btn-brand btn-small comment-cancel">Cancel</button></div>';

    $(parentDt).prev('dd').attr('contenteditable', 'True').addClass('editable-comment');
    $(parentDt).prev('dd').after(editableControlsHtml);
    $('.editable-comment').data('oldComment', $('.edit-controls').prev().text());
    $('.editable-comment').focus();
    $(parentDt).hide();

});

$(document).on('click', '.comment-cancel', function (e) {
    e.preventDefault();
    cancelHtmlRender();
});

$(document).on('click', '.comment-save', function (e) {
    e.preventDefault();

    var editableControls = $('.edit-controls'),
        editableDd = $(editableControls).prev(),
        updatedComment = $(editableDd).text(),
        oldComment = $('.editable-comment').data('oldComment');

    if (updatedComment === ''){
        $(editableDd).focus();
        return
    }

     if (updatedComment === oldComment) {
        cancelHtmlRender();
        return
    }

    $.ajax({
        type: "PATCH",
        url: $(editableControls).next().find('button').data('url'),
        data: {'comment': updatedComment},
        success: function (response) {
            var formattedDatetime;
            removeEditable(editableControls, editableDd);
            $(editableDd).text(response['comment']);

            //format datetime e.g. February 08, 2017, 13:36:45 p.m.
            formattedDatetime = $.format.date(response['modified'], 'MMMM dd, yyyy, hh:mm p');
            $(editableDd).prev('dt').find('span.datetime').text(formattedDatetime);
        },
        error: function () {
            alert("Unable to edit comment this time, Please try again later.");
            removeEditable(editableControls, editableDd);

        }
    });

});

function cancelHtmlRender(){
    var editableControls = $('.edit-controls'),
        editableDd = $(editableControls).prev();

    editableDd.text($('.editable-comment').data('oldComment'));
    editableControls.hide();
    removeEditable(editableControls, editableDd)
}

function removeEditable(editableControls, editableDd) {
   $(editableControls).remove();
   $(editableDd).removeAttr('contenteditable').removeClass('editable-comment');
   $(editableDd).next('dt').show();
}
