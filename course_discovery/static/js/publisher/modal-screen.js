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

        $('#instructorProfileModal div.full_name').html(data.full_name);
        $('#instructorProfileModal div.organization').html(data.organization);
        $('#instructorProfileModal img.image_url').attr('src', data.image_url);
        $('#instructorProfileModal a.btn-download').attr('href', data.image_url);
        $('#instructorProfileModal div.position').html(data.position);
        $('#instructorProfileModal div.bio').html(data.bio);
        $('#instructorProfileModal div.major-works').html(data.major_works);

        data.social_networks.forEach(function(socialNetwork) {
            var socialLinkHtml = '<div class="instructor-list-item-view">';
            if (socialNetwork.title) socialLinkHtml += socialNetwork.title + ': ';
            socialLinkHtml += '<a target="_blank">' + socialNetwork.url + '</a>';
            socialLinkHtml += '</div>';
            $('.social-links').append(socialLinkHtml);
        });
        data.areas_of_expertise.forEach(function(areaOfExpertise) {
            var areaOfExpertiseHtml = '<div class="instructor-list-item-view"><p>' + areaOfExpertise.value + '</p></div>';
            $('.areas-of-expertise').append(areaOfExpertiseHtml);
        });

        assignData('.profile_url', data.profile_url);
    });
});

function closeModal(event, modal) {
    event.preventDefault();
    if (modal.attr('id') == 'addInstructorModal') {
        resetInstructorModalData();
    }
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
    $('.instructor-list-item-view').remove();

    assignData('.profile_url', '#');
}

function assignData(element, data){
    $(element).attr("href", data);
    $(element + '_copy').html(data);
}

function resetInstructorModalData() {
    var imgPath = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==',
    selectors = ['#given-name', '#family-name', '#title', '#bio', '#majorWorks'];
    $('#addInstructorModal div img').attr('src',imgPath);
    for (var i in selectors) clearData(selectors[i]);
    $('.social-link').remove();
    $('.area-of-expertise').remove();
}

function clearData(selector){
    $('#addInstructorModal div '+ selector).val('');
}
