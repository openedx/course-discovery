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
        $('#instructorProfileModal div.position').html(data['position']);
        $('#instructorProfileModal div.bio').html(data['bio']);
        $('#instructorProfileModal div.email').html(data['email']);

        assignData('.profile_url', data['profile_url']);
        assignData('.facebook_url', data['social_networks']['facebook']);
        assignData('.twitter_url', data['social_networks']['twitter']);
        assignData('.blog_url', data['social_networks']['blog']);

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
    $('#instructorProfileModal img.image_url').attr('src','#');
    $('#instructorProfileModal div.position').html('');
    $('#instructorProfileModal a.btn-download').attr('href', '#');
    $('#instructorProfileModal div.bio').html('');

    assignData('.facebook_url', '#');
    assignData('.twitter_url', '#');
    assignData('.profile_url', '#');
    assignData('.blog_url', '#');
}

function assignData(element, data){
    $(element).attr("href", data);
    $(element + '_copy').html(data);
}
