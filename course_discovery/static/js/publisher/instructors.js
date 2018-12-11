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
            socialLinks,
            urlsDetailed,
            socialLinkError,
            requestType,
            personData,
            url = $(this).data('url'),
            uuid = $('#addInstructorModal').data('uuid');

        if (!editMode && $('#staffImageSelect').get(0).files.length === 0 ) {
            addModalError(gettext("Please upload a instructor image."));
            return;
        }

        socialLinks = getSocialLinks();
        urlsDetailed = socialLinks.socialLinksArray;
        socialLinkError = socialLinks.error;
        if (socialLinkError) {
            addModalError(socialLinkError);
            return;
        }
        areasOfExpertiseObj = getAreasOfExpertise();
        areasOfExpertise = areasOfExpertiseObj.areasOfExpertiseArray;
        areasOfExpertiseError = areasOfExpertiseObj.error;
        if (areasOfExpertiseError) {
            addModalError(areasOfExpertiseError);
            return;
        }
        personData = {
            'given_name': $('#given-name').val(),
            'family_name': $('#family-name').val(),
            'bio': $('#bio').val(),
            'profile_image': $('.select-image').attr('src'),
            'position': getFormInstructorPosition(),
            'major_works': $('#majorWorks').val(),
            'urls_detailed': urlsDetailed,
            'areas_of_expertise': areasOfExpertise,
        };

        if (editMode) {
            requestType = "PATCH";
            personData.uuid = uuid;
            url = url + uuid + '/';

            if (!$('.select-image').hasClass('image-updated')) {
                delete personData.profile_image;
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
                clearModalError();
                closeModal(e, $('#addInstructorModal'));
                if (editMode) {
                    loadInstructor(response.uuid, editMode)
                } else {
                    loadInstructor(response.uuid)
                }
            },
            error: function (response) {
                addModalError(gettext("Something went wrong!"));
                console.log(response);
            }
        });
    });
});

var newElementCount = 1;
$(document).on('click', '.add-instructor-list-item-btn', function (e) {
    var $btn = $(e.target)
    e.preventDefault();
    // We are prepending new instructor list items with the string new to distinguish between newly
    // created items and existing ones. When sending these to the backend, we will be able
    // to indicate whether an item should be updated or created.
    if ($btn.hasClass('js-add-social-link-btn')) { addNewSocialLink('new' + newElementCount); }
    else if ($btn.hasClass('js-add-area-of-expertise-btn')) { addNewAreaOfExpertise('new' + newElementCount); }
    newElementCount++;
});


$(document).on('click', '.remove-instructor-list-item-btn', function (e) {
    $(e.target.parentElement).remove();
});

function addNewSocialLink(id, type, title, url) {
    var id = id || '',
        type = type || '',
        title = title || '',
        url = url || '',
        socialLinksWrapper = $('.js-social-links-wrapper'),
        linkHtml = '<div class="social-link" data-id="' + id + '">\
                        <label class="instructor-list-field" for="social-link-type-' + id + '">' + gettext('Type') +
                            '<select class="instructor-list-input social-link-select-type" name="link-type" \
                            id="social-link-type-' + id + '">\
                                <option disabled selected></option>\
                                <option value="facebook">' + gettext('Facebook') + '</option>\
                                <option value="twitter">' + gettext('Twitter') + '</option>\
                                <option value="blog">' + gettext('Blog') + '</option>\
                                <option value="others">' + gettext('Other') + '</option>\
                            </select>\
                        </label>\
                        <label class="instructor-list-field" for="social-link-title-' + id + '">' + gettext('Title') +
                            '<span class="optional"> - ' + gettext('optional') + '</span>\
                            <input class="instructor-list-input field-input input-text" type="text" id="social-link-title-' + id + '"/>\
                        </label>\
                        <label class="instructor-list-field" for="social-link-url-' + id + '">' + gettext('URL') +
                            '<input class="instructor-list-input field-input input-text" type="text" id="social-link-url-' + id + '"/>\
                        </label>\
                        <button class="remove-instructor-list-item-btn fa fa-close"></button>\
                    </div>';

    socialLinksWrapper.append(linkHtml);
    $('#social-link-type-' + id).val(type);
    $('#social-link-title-' + id).val(title);
    $('#social-link-url-' + id).val(url);
}

function getSocialLinks() {
    var socialLinksArray = [],
        socialLinks = $('.social-link'),
        error = '',
        id,
        type,
        title,
        url,
        uniquenessTest = [];
    for (var i = 0; i < socialLinks.length; i++) {
        type = $('#social-link-type-' + socialLinks[i].dataset.id).val();
        title = $('#social-link-title-' + socialLinks[i].dataset.id).val();
        url = $('#social-link-url-' + socialLinks[i].dataset.id).val();
        id = socialLinks[i].dataset.id;

        if (type === null || url === '') {
            error = gettext('Please specify a type and url for each social link.');
            return {
                socialLinksArray: socialLinksArray,
                error: error
            };
        }

        // There is a uniqueness constraint on titles and types
        for (var j = 0; j < uniquenessTest.length; j++) {
            existingLink = uniquenessTest[j];
            if (title === existingLink.title && type === existingLink.type) {
                error = gettext('Social links with the same type must have different titles.');
                return {
                    socialLinksArray: socialLinksArray,
                    error: error
                };
            }
        }
        uniquenessTest.push({'title': title, 'type': type});

        // see comment under on click of #add-social-link-btn
        if (id.includes('new')) id = '';

        socialLinksArray.push({
            'id': parseInt(id),
            'type': type,
            'title': title,
            'url': url,
        });
    }
    return {
        socialLinksArray: socialLinksArray,
        error: error
    };
}

function addNewAreaOfExpertise(id, value) {
    var id = id || '',
        value = value || '',
        areasOfExpertiseWrapper = $('.js-areas-of-expertise-wrapper'),
        linkHtml = '<div class="area-of-expertise" data-id="' + id + '">\
                        <label class="instructor-list-field" for="area-of-expertise-value-' + id + '">' +
                        gettext('Area of Expertise') +
                            '<input class="instructor-list-input field-input input-text" type="text"\
                            id="area-of-expertise-value-' + id + '"/>\
                        </label>\
                        <button class="remove-instructor-list-item-btn fa fa-close"></button>\
                    </div>';

    areasOfExpertiseWrapper.append(linkHtml);
    $('#area-of-expertise-value-' + id).val(value);
}

function getAreasOfExpertise() {
    var areasOfExpertiseArray = [],
        areasOfExpertise = $('.area-of-expertise'),
        error = '',
        value;
    for (var i = 0; i < areasOfExpertise.length; i++) {
        value = $('#area-of-expertise-value-' + areasOfExpertise[i].dataset.id).val();
        id = areasOfExpertise[i].dataset.id;

        if (value === '') {
            error = gettext('Please specify a value for each area of expertise.');
            return {
                areasOfExpertiseArray: areasOfExpertiseArray,
                error: error
            };
        }

        // see comment under on click of #add-area-of-expertise-btn
        if (id.includes('new')) id = '';

        areasOfExpertiseArray.push({
            'id': parseInt(id),
            'value': value,
        });
    }
    return {
        areasOfExpertiseArray: areasOfExpertiseArray,
        error: error
    };
}

function getFormInstructorPosition () {
    var org_override_element_value = $('#organization_override').val(),
        instructor_position = $('#title').val();

    if (org_override_element_value && ($('#org_override_container').is(':visible'))) {
        return {
            title: instructor_position,
            organization_override: org_override_element_value,
            organization: null
        };
    }
    return {
        title: instructor_position,
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
                        if (image.width !== imageDimension || image.height !== imageDimension) {
                            addModalError(
                                gettext("The image dimensions must be " + imageDimension + "×" + imageDimension)
                            );
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
            if (data.results.length) {
                // with uuid there will be only one instructor
                instructor = data.results[0];
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
            if (data.position == null){
                $('#org_override_container').hide();
                $('#org_container').show();
            }
            else if (data.position.organization_id == null){
                $('#organization_override').val(data.position.organization_override);
                $('#title').val(data.position.title);
                $('#org_container').hide();
                $('#org_override_container').show();
            }
            else {
                $('#id_organization').val(data.position.organization_id);
                $('#title').val(data.position.title);
                $('#org_override_container').hide();
                $('#org_container').show();
            }
            $('.select-image').attr('src', data.profile_image_url);
            $('#given-name').val(data.given_name);
            $('#family-name').val(data.family_name);
            $('#bio').val(data.bio);
            $('#majorWorks').val(data.major_works);
            for (var i = 0; i < data.urls_detailed.length; i++) {
                addNewSocialLink(
                    data.urls_detailed[i].id,
                    data.urls_detailed[i].type,
                    data.urls_detailed[i].title,
                    data.urls_detailed[i].url,
                );
            }
            for (var i = 0; i < data.areas_of_expertise.length; i++) {
                addNewAreaOfExpertise(
                    data.areas_of_expertise[i].id,
                    data.areas_of_expertise[i].value,
                );
            }
        }
    });
});
