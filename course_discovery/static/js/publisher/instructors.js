$(document).ready(function () {

    $("#id_staff").on("select2:select", function (e) {
        var $instructorSelector = e.params.data,
            id = $instructorSelector.id,
            selectedInstructorData = $.parseHTML($instructorSelector.text)[0],
            image_source = $(selectedInstructorData).find('img').attr('src'),
            name = $(selectedInstructorData).find('b').text(),
            uuid = $(selectedInstructorData)[0].id,
            organization_id = $(selectedInstructorData).find('span').text(),
            edit_instructor = $(selectedInstructorData).data('can-edit');
        renderSelectedInstructor(id, name, image_source, uuid, organization_id, edit_instructor);

    });

    $("#override_toggle").click(function (e) {
        $('#org_override_container').toggle();
        $('#org_container').toggle();
    });

    $('#add-new-instructor').click(function (e) {
        clearModalError();
        var btnInstructor = $('#add-instructor-btn');
        $('#org_container').show();
        $('#org_override_container').hide();
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

        if (!editMode && $('#staffImageSelect').get(0).files.length === 0 ) {
            addModalError(gettext("Please upload a instructor image."));
            return;
        }
        var position = getFormInstructorPosition()

        personData = {
            'given_name': $('#given-name').val(),
            'family_name': $('#family-name').val(),
            'bio': $('#bio').val(),
            'email': $('#email').val(),
            'profile_image': $('.select-image').attr('src'),
            'position': position,
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

function getFormInstructorPosition () {
    if ($('#organization_override').val()) {
        return {
            title: $('#title').val(),
            organization_override: $('#organization_override').val(),
            organization: null
        };
    }
    return {
        title: $('#title').val(),
        organization_override: null,
        organization: parseInt($('#id_organization').val())
    };
}

function loadSelectedImage (input) {
    var maxFileSize = 256, // Size in KB's
        imageFile = input.files[0],
        imageDimension = 110,
        imgPath = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';
    if (imageFile) {
        if ( (/\.(png|jpeg|jpg|gif)$/i).test(imageFile.name) ) {
            if (imageFile.size / 1024 > maxFileSize) {
                addModalError(gettext("The image size must be smaller than 256kb"));
            }
            else {
                var reader = new FileReader();
                clearModalError();

                reader.addEventListener("load", function (e) {
                    var image = new Image();
                    image.addEventListener("load", function () {
                        if (image.width > imageDimension && image.height > imageDimension) {
                            addModalError(gettext("The image dimensions must be less than 110 x 110"));
                            $('.select-image').attr('src', imgPath).removeClass('image-updated');
                            $('#staffImageSelect').val('');
                        }
                    });
                    $('.select-image').attr('src', e.target.result).addClass('image-updated');
                    image.src = reader.result;
                });
                reader.readAsDataURL(imageFile);
            }
        }
        else{
            addModalError(gettext(imageFile.name +" Unsupported Image extension" ));
        }
    }
}

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
    $('#staff_' + id).remove();
    this.closest('.selected-instructor, .instructor').remove();
    $('.instructor-select').find('.select2-selection__choice').remove();
});

function renderSelectedInstructor(id, name, image, uuid, organization_id, edit_instructor) {
    var user_organizations_ids = $('#user_organizations_ids').text(),
        course_user_role = $('#course_user_role').text(),
        is_internal_user = $('#is_internal_user').text(),
        staff = '<input type="hidden" id="staff_' + id +  '"name="staff" value="' + id + '">',
        instructorHtmlStart = '<div class="instructor" id= "instructor_' + id + '"><div><img src="' + image + '"></div><div>',
        instructorHtmlEnd = '<b>' + name + '</b></div></div>',
        controlOptions = '<a class="delete" id="' + id + '"href="#"><i class="fa fa-trash-o fa-fw"></i></a>';


    var user_is_course_team = course_user_role === "course_team";
    if (organization_id != "None" && user_organizations_ids != "[]"){
        var user_is_in_similar_org_as_instructor = $.inArray(parseInt(organization_id), JSON.parse(user_organizations_ids)) > -1;
    }
    else {
        var user_is_in_similar_org_as_instructor = false;
    }
    var org_is_none = organization_id === "None";

    if ((user_is_course_team && (user_is_in_similar_org_as_instructor && uuid || org_is_none)) || is_internal_user || edit_instructor) {
        controlOptions += '<a class="edit" id="' + uuid + '"href="#"><i class="fa fa-pencil-square-o fa-fw"></i></a>';
    }
    $('.selected-instructor').append(staff + instructorHtmlStart + controlOptions + instructorHtmlEnd);
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
        name,
        instructor_id,
        organization_id,
        edit_instructor;

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
                organization_id = $(label).find('span').text();
                edit_instructor = $(label).data('can-edit');

                if (editMode) {
                    // Updating the existing instructor
                    instructor_id = $('#instructor_' + id);
                    instructor_id.find('img').attr('src', image_source);
                    instructor_id.find('b').text(name);
                }
                else {
                    renderSelectedInstructor(id, name, image_source, uuid, organization_id, edit_instructor);
                }
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
            if (data['position']['organization_id'] == null){
                $('#organization_override').val(data['position']['organization_override']);
                $('#org_container').hide();
            }
            else {
                $('#id_organization').val(data['position']['organization_id']);
                $('#org_override_container').hide()
            }
            $('.select-image').attr('src', data['profile_image_url']);
            $('#given-name').val(data['given_name']);
            $('#family-name').val(data['family_name']);
            $('#title').val(data['position']['title']);
            $('#email').val(data['email']);
            $('#bio').val(data['bio']);
            $('#majorWorks').val(data['works'].join('\n'));
            $('#facebook').val(data['urls']['facebook']);
            $('#twitter').val(data['urls']['twitter']);
            $('#blog').val(data['urls']['blog']);
        }
    });
});
