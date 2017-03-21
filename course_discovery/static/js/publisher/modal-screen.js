$(document).ready(function(){

    $(document).click(function(e){
        var modal = $('.modal');
        if (event.target == modal[0]) {
            closeModal(e, modal);
        }
    });

    $('.closeModal').click(function (e) {
        closeModal(e, $('.modal'));
    });

    $('.btn-course-edit').click(function(e){
        $('#editWarningModal').show();
        $('body').addClass('stopScroll');
    });

    $('.btn-courserun-edit').click(function(e){
        $('#editCourseRun').show();
        $('body').addClass('stopScroll');
    });

    $('.btn-preview-accept').click(function(e){
        $('#acceptPreviewModal').show();
        $('body').addClass('stopScroll');
    });
});

function closeModal(event, modal) {
    event.preventDefault();
    modal.hide();
    $('body').removeClass('stopScroll');
}

function addModalError(errorMessage) {
    var errorHtml = '<div class="alert alert-error" role="alert" aria-labelledby="alert-title-error" tabindex="-1">' +
        '<div><p class="alert-copy">' + errorMessage + '</p></div></div>';

    $('#modal-errors').html(errorHtml);
    $('#modal-errors').show();
}

function clearModalError($modal) {
    $('#modal-errors').html('');
    $('#modal-errors').hide();
}
