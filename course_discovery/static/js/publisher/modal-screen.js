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

    $('.btn-instructor-detail').click(function(e){
        event.preventDefault();
        var data = staffData[$(this).data('staff_id')];
        $('#instructorProfileModal').show();
        $('body').addClass('stopScroll');
        resetModalData();

        $('#instructorProfileModal div.full_name').html(data['full_name']);
        $('#instructorProfileModal div.organization').html(data['organization']);
        $('#instructorProfileModal img.image_url').attr('src', data['image_url']);
        $('#instructorProfileModal a.btn-download').attr('href', data['image_url']);

        if (data['profile_url']) {
            $('#instructorProfileModal a.profile_url').attr("href", data['profile_url']);
            $('#instructorProfileModal div.profile_url_copy').html(data['profile_url']).hide();
        }
        else
           $('#instructorProfileModal a.profile_url').attr("href", '#');

        $('#instructorProfileModal div.position').html(data['position']);
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
    $('.modal').scrollTop(0);
}

function clearModalError($modal) {
    $('#modal-errors').html('');
    $('#modal-errors').hide();
}

function resetModalData() {
    $('#instructorProfileModal div.full_name').html('');
    $('#instructorProfileModal div.organization').html('');
    $('#instructorProfileModal img.image_url').attr('src','');
    $('#instructorProfileModal a.btn-download').attr('href', '');
    $('#instructorProfileModal a.profile_url').attr("href", '');
    $('#instructorProfileModal div.profile_url_copy').html('');
    $('#instructorProfileModal div.position').html('');
}
