$(document).ready(function() {
    var box = $('#id_comment');
   $("#id_submit").click(function(event){
       if( !box.val() ) {
            box.addClass('has-error');
            box.focus();
        }
       else{
           $("#frm_comment").submit();
       }

   });
});

$(document).on('click', '.comment-edit', function (e) {
    e.preventDefault();
    var parentDt = this.closest('dt'),
        editableControlsHtml = '<div class="edit-controls"><button class="btn-brand btn-small comment-save">Save</button>' +
            '<button class="btn-brand btn-small comment-cancel">Cancel</button></div>';

    $(parentDt).next('dd').attr('contenteditable', 'True').addClass('editable-comment');
    $(parentDt).after(editableControlsHtml);
    $('.editable-comment').data('oldComment', $('.edit-controls').next().text());

    $(parentDt).hide();
});

$(document).on('click', '.comment-cancel', function (e) {
    e.preventDefault();

    var editableControls = $('.edit-controls'),
        editableDd = $(editableControls).next();

    editableDd.text($('.editable-comment').data('oldComment'));
    editableControls.hide();
    removeEditable(editableControls, editableDd)
});

$(document).on('click', '.comment-save', function (e) {
    e.preventDefault();

    var editableControls = $('.edit-controls'),
        editableDd = $(editableControls).next(),
        updatedComment = $(editableDd).text();

    $.ajax({
        type: "PATCH",
        url: $(editableControls).prev().find('button').data('url'),
        data: {'comment': updatedComment},
        success: function (response) {
            var formattedDatetime;
            removeEditable(editableControls, editableDd);
            $(editableDd).text(response['comment']);

            //format datetime e.g. Dec. 15, 2016, 10:03 a.m.
            formattedDatetime = $.format.date(response['modified'], 'MMM. dd, yyyy, hh:mm p');
            $(editableDd).prev().find('span.datetime').text(formattedDatetime);
        },
        error: function () {
            alert("Unable to edit comment this time, Please try again later.");
            removeEditable(editableControls, editableDd);

        }
    });

});

function removeEditable(editableControls, editableDd) {
    $(editableControls).remove();
    $(editableDd).removeAttr('contenteditable').removeClass('editable-comment');
    $(editableDd).prev().show();
}
