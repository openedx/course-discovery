$(document).ready(function(){

    $('#add-new-instructor').click(function(e){
        $('#addInstructorModal').show();
        $('body').addClass('stopScroll');
    });

    $('#add-instructor-btn').click(function (e) {
        $.ajax({
            type: "POST",
            url: $(this).data('url'),
            data: {
                'data': JSON.stringify(
                    {
                        'given_name': $('#given-name').val(),
                        'family_name': $('#family-name').val(),
                        'bio': $('#bio').val(),
                        'profile_image': $('.select-image').attr('src'),
                        'position':{
                            'title': $('#title').val(),
                            'organization': parseInt($('#id_organization').val())
                        },
                        'works': $('#majorWorks').val().split('\n'),
                        'urls': {
                            'facebook': $('#facebook').val(),
                            'twitter': $('#twitter').val(),
                            'blog': $('#blog').val()
                        }
                    }
                )
            },
            success: function (response) {
                $('#given-name').val('');
                $('#family-name').val('');
                $('#title').val('');
                $('#bio').val('');
                $('.select-image').attr('src', '');
                $('#majorWorks').val('');
                $('#facebook').val('');
                $('#twitter').val('');
                $('#blog').val('');
                clearModalError();
                closeModal(e, $('#addInstructorModal'));
                loadInstructor(response['uuid'])
            },
            error: function (response) {
                addModalError(gettext("Something went wrong!"));
                console.log(response);
            }
        });
    });


    $("#id_staff").find('option:selected').each(function(){
        var id = this.value,
            label = $.parseHTML(this.label),
            image_source = $(label[0]).attr('src'),
            name = $(label[1]).text();
        renderSelectedInstructor(id, name, image_source);
    });

    $('.remove-image').click(function (e) {
        e.preventDefault();
        $('.course-image-input').removeClass('hidden');
        $('.course-image-thumbnail').hide();
        $('.course-image-field a').hide();
        $('input#image-clear_id').prop('checked', true);
    });

    // If file selected mark checkbox unchecked otherwise checked.
    $('input#id_image').change(function (e) {
        var clearImageInput = $('input#image-clear_id');
        e.preventDefault();
        if (this.files && this.files[0]) {
            clearImageInput.prop('checked', false);
        } else {
            clearImageInput.prop('checked', true);
        }

    });
});

function loadAdminUsers(org_id) {
    $.getJSON({
        url: '/publisher/api/admins/organizations/'+ org_id +'/users/',
        success: function (data) {
            var teamAdminDropDown = $('#id_team_admin'),
                selectedTeamAdmin = $('#id_team_admin option:selected').val(),
                organizationInputType = $('#id_organization').attr('type');
            teamAdminDropDown.empty();

            if (organizationInputType == 'hidden' ) {
                teamAdminDropDown.append('<option>---------</option>');
            } else {
                // it will looks same like other django model choice fields
                teamAdminDropDown.append('<option selected="selected">---------</option>');
            }

            $.each(data.results, function (i, user) {
                if (selectedTeamAdmin == user.id && organizationInputType === 'hidden' ) {
                    teamAdminDropDown.append(
                        $('<option selected="selected"> </option>').val(user.id).html(user.full_name)
                    );
                } else {
                    teamAdminDropDown.append($('<option> </option>').val(user.id).html(user.full_name));
                }
            });
        }
    });
}

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
                $('.select-image').attr('src', e.target.result);
            };

            reader.readAsDataURL(input.files[0]);
        }
    }
}

function closeModal(event, modal) {
    event.preventDefault();
    modal.hide();
    $('body').removeClass('stopScroll');
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


$(document).on('click', '.selected-instructor a', function (e) {
    e.preventDefault();
    var id = this.id,
        option = $('#id_staff').find('option[value="' + id + '"]');

    option.prop("selected", false);
    this.closest('.selected-instructor, .instructor').remove();
});

function renderSelectedInstructor(id, name, image) {
    var instructorHtml = '<div class="instructor"><div><img src="' + image + '"></div><div><a id="' + id + '" ' +
        'href="#"><i class="fa fa-trash-o fa-fw"></i></a><b>' + name + '</b></div></div>';

    $('.selected-instructor').append(instructorHtml);
}

function toggleMicroMaster (checked) {
    // If is-micromaster checkbox value true from db then show the x-micromaster block.
    $('#micromasters_name_group').toggle(checked);
}

function toggleXseries(checked) {
    // If is-xseries checkbox value true from db then show the x-series block.
    $('#xseries_name_group').toggle(checked);
}

$(document).on('change', '#id_type', function (e) {
    var $seatBlock = $("#SeatPriceBlock"),
        selectedSeatType = this.value;
    if (selectedSeatType === 'audit' || selectedSeatType === '') {
        $seatBlock.hide();
    } else{
        $seatBlock.show();
    }
});




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

function loadInstructor(uuid) {
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
                renderSelectedInstructor(id, name, image_source);
            }

        }
    });
}
