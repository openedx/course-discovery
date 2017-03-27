$(document).ready(function(){

    $("#id_staff").find('option:selected').each(function(){
        var id = this.value,
            label = $.parseHTML(this.label),
            image_source = $(label[0]).attr('src'),
            name = $(label[1]).text();
        renderSelectedInstructor(id, name, image_source);
    });

    $('#add-new-instructor').click(function(e){
        clearModalError();
        $('#addInstructorModal').show();
        $('body').addClass('stopScroll');
    });

    $('#add-instructor-btn').click(function (e) {

        if ($('#staffImageSelect').get(0).files.length === 0){
            addModalError(gettext("Please upload a instructor image. File must be smaller than 1 megabyte in size."));
            return false;
        }

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
                $('.select-image').attr('src', e.target.result);
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
