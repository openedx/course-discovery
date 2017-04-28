$(document).ready(function(){

    $("#id_staff").find('option:selected').each(function(){
        var id = this.value,
            label = $.parseHTML(this.label),
            image_source = $(label[0]).attr('src'),
            name = $(label[1]).text();
            uuid = $(label[1]).data('uuid');
        renderSelectedInstructor(id, name, image_source, uuid);
    });

    $('#add-new-instructor').click(function(e){
        clearModalError();
        var btnInstructor = $('#add-instructor-btn');
        $('#addInstructorModal').show();
        $('body').addClass('stopScroll');
        $('.new-instructor-heading').text(gettext('New Instructor'));
        btnInstructor.removeClass('edit-mode');
        btnInstructor.text(gettext('Add staff member'));
    });

    $('#add-instructor-btn').click(function (e) {
        var editMode = $(this).hasClass('edit-mode'),
            requestType,
            personData,
            url = $(this).data('url'),
            uuid = $('#addInstructorModal').data('uuid');

        if (!editMode && $('#staffImageSelect').get(0).files.length === 0){
            addModalError(gettext("Please upload a instructor image. File must be smaller than 1 megabyte in size."));
            return false;
        }
        personData = {
            'given_name': $('#given-name').val(),
            'family_name': $('#family-name').val(),
            'bio': $('#bio').val(),
            'email': $('#email').val(),
            'profile_image': $('.select-image').attr('src'),
            'position': {
                title: $('#title').val(),
                organization: parseInt($('#id_organization').val())
            },
            'works': $('#majorWorks').val().split('\n'),
            'urls': {
                facebook: $('#facebook').val(),
                twitter: $('#twitter').val(),
                blog: $('#blog').val()
            }
        };

        if (editMode) {
            requestType = "PATCH";
            personData['uuid'] = uuid;
            url = url + uuid + '/';

            if (!$('.select-image').hasClass('image-updated')) {
                delete personData['profile_image'];
            }

        } else {
            requestType = "POST";
        }

        $.ajax({
            type: requestType,
            url: url,
            contentType: "application/json",
            data: JSON.stringify(personData),
            success: function (response) {
                $('#given-name').val('');
                $('#family-name').val('');
                $('#title').val('');
                $('#bio').val('');
                $('.select-image').attr('src', '').removeClass('image-updated');
                $('#majorWorks').val('');
                $('#facebook').val('');
                $('#twitter').val('');
                $('#blog').val('');
                clearModalError();
                closeModal(e, $('#addInstructorModal'));
                if (editMode) {
                    loadInstructor(response['uuid'], editMode)
                } else {
                    loadInstructor(response['uuid'])
                }
            },
            error: function (response) {
                addModalError(gettext("Something went wrong!"));
                console.log(response);
            }
        });
    });
});

function loadSelectedImage(input) {
    // 1mb in bytes
    var maxFileSize = 1000000;

    if (input.files && input.files[0]) {
        if (input.files[0].size > maxFileSize) {
            addModalError(gettext("File must be smaller than 1 megabyte in size."));
        } else {
            var reader = new FileReader();

            clearModalError();
            reader.onload = function (e) {
                $('.select-image').attr('src', e.target.result).addClass('image-updated');
            };

            reader.readAsDataURL(input.files[0]);
        }
    }
}

$(document).on('change', '#id_staff', function (e) {

    var $instructorSelector = $('.instructor-select'),
        $instructor = $instructorSelector.find('.select2-selection__choice'),
        id = $instructor.find('.instructor-option').last().prop("id"),
        image_source,
        name;
    $instructorSelector.find('.select2-selection__clear').remove();
    image_source = $instructor.find('img').last().attr('src');
    name = $instructor.find('b').last().text();
    renderSelectedInstructor(id, name, image_source);
    $instructor.remove();
});


$(document).on('click', '.selected-instructor a.delete', function (e) {
    e.preventDefault();
    var id = this.id,
        $staff = $('#id_staff'),
        option = $staff.find('option[value="' + id + '"]');
    // This condition is to check for the existence of id or uuid
    if (option.length == 0) {
        option = $staff.find('option:contains("' + id + '")');
    }
    option.remove();
    this.closest('.selected-instructor, .instructor').remove();
    $('.instructor-select').find('.select2-selection__choice').remove();
});

function renderSelectedInstructor(id, name, image, uuid) {
    var instructorHtmlStart = '<div class="instructor"><div><img src="' + image + '"></div><div>',
        instructorHtmlEnd = '<b>' + name + '</b></div></div>',
        controlOptions = '<a class="delete" id="' + id + '"href="#"><i class="fa fa-trash-o fa-fw"></i></a>';

    if (uuid) {
        controlOptions += '<a class="edit" id="' + uuid + '"href="#"><i class="fa fa-pencil-square-o fa-fw"></i></a>';
    }

    $('.selected-instructor').append(instructorHtmlStart + controlOptions + instructorHtmlEnd);
}

$(document).on('click', '.btn-save-preview-url', function (e) {
    preview_url = $('#id-review-url').val();
    if (!preview_url) {
        showInvalidPreviewUrlError();
        return
    }
    $.ajax({
        type: "PATCH",
        url: $(this).data('url'),
        data: JSON.stringify({'preview_url': preview_url}),
        contentType: "application/json",
        success: function (response) {
            location.reload();
        },
        error: function (response) {
            showInvalidPreviewUrlError();
        }
    });
});

function loadInstructor(uuid, editMode) {
    var url = $('#id_staff').attr('data-autocomplete-light-url') + '?q=' + uuid,
        instructor,
        id,
        label,
        image_source,
        name;

    $.getJSON({
        url: url,
        success: function (data) {
            if (data['results'].length) {
                // with uuid there will be only one instructor
                instructor = data['results'][0];
                id = instructor.id;
                label = $.parseHTML(instructor.text);
                image_source = $(label).find('img').attr('src');
                name = $(label).find('b').text();
                $('#id_staff').append($("<option/>", {
                    value: id,
                    text: name
                }).attr('selected', 'selected'));

                if (editMode) {
                    //before loading updated instructor it will remove old one.
                    $('#' + id).click();
                }
                renderSelectedInstructor(id, name, image_source, uuid);
            }

        }
    });
}

$(document).on('click', '.selected-instructor a.edit', function (e) {
    e.preventDefault();
    var uuid = this.id,
        btnInstructor = $('#add-instructor-btn'),
        instructorModal = $('#addInstructorModal');

    $('body').addClass('stopScroll');
    instructorModal.show();
    instructorModal.data('uuid', uuid);
    btnInstructor.addClass('edit-mode');
    btnInstructor.text(gettext('Update staff member'));
    $('.new-instructor-heading').text(gettext('Update Instructor'));

    $.getJSON({
        url: btnInstructor.data('url') + uuid,
        success: function (data) {
            $('.select-image').attr('src', data['profile_image']['medium']['url']);
            $('#given-name').val(data['given_name']);
            $('#family-name').val(data['family_name']);
            $('#title').val(data['position']['title']);
            $('#bio').val(data['bio']);
            $('#majorWorks').val(data['works'].join('\n'));
            $('#facebook').val(data['urls']['facebook']);
            $('#twitter').val(data['urls']['twitter']);
            $('#blog').val(data['urls']['blog']);
        }
    });
});
