$(document).ready(function(){
    $(".administration-nav .tab-container > button").click(function(event) {
        event.preventDefault();
        $(this).addClass("selected");
        $(this).siblings().removeClass("selected");
        var tab = $(this).data("tab");
        $(".tab-content").not(tab).css("display", "none");
        $(tab).fadeIn();
    });

    $('ul.tabs .course-tabs').click(function(){
        var tab_id = $(this).attr('data-tab'),
            $tabContent = $("#"+tab_id);
        $(this).parent().find('.course-tabs').removeClass('active');
        $tabContent.parent().find('.content').removeClass('active');

        $(this).addClass('active');
        $tabContent.addClass('active');
    });

    $("#change-admin").click(function (e) {
        e.preventDefault();
        $(".field-admin-name").hide();
        $("#field-team-admin").show();
    });

    var org_id = $('#organization-name').data('org_id');
    if (org_id){
        loadAdminUsers(org_id);
    }

    var microMaster = $('#id_is_micromasters'),
        xseries = $('#id_is_xseries');

    if (microMaster.is(':checked')) {
        toggleMicroMaster(true);
    }
    if (xseries.is(':checked')) {
        toggleXseries(true);
    }
    microMaster.click( function(){
        toggleMicroMaster(this.checked);
    });
    xseries.click( function(e){
        toggleXseries(this.checked)
    });
    $('#add-new-instructor').click(function(e){
        $('#addInstructorModal').show();
        $('body').addClass('stopScroll');
    });
    $(document).click(function(e){
        var modal = $('#addInstructorModal');
        if (event.target == modal[0]) {
            closeModal(e, modal);
        }
    });
    $('.closeModal').click(function (e) {
        closeModal(e, $('#addInstructorModal'));
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

$(document).on('change', '#id_organization', function (e) {
    var org_id = this.value;

    // it will reset the select input
    $("#id_team_admin").prop("selectedIndex", 0);
    if (org_id) {
        loadAdminUsers(org_id);
    }
});

function loadAdminUsers(org_id) {
    $.getJSON({
        url: '/publisher/api/admins/organizations/'+ org_id +'/users/',
        success: function (data) {
            var teamAdminDropDown = $('#id_team_admin');
            teamAdminDropDown.empty();

            // it will looks same like other django model choice fields
            teamAdminDropDown.append('<option selected="selected">---------</option>');

            $.each(data.results, function (i, user) {
                teamAdminDropDown.append($('<option> </option>').val(user.id).html(user.full_name));
            });
        }
    });
}

function loadSelectedImage(input) {
    if (input.files && input.files[0]) {
        var reader = new FileReader();

        reader.onload = function (e) {
            $('.select-image').attr('src', e.target.result);
        };

        reader.readAsDataURL(input.files[0]);
    }
}

function closeModal(event, modal) {
    event.preventDefault();
    modal.hide();
    $('body').removeClass('stopScroll');
}

$(document).on('change', '#id_staff', function (e) {

    var id = this.value,
        $instructorSelector = $('.instructor-select'),
        $instructor = $instructorSelector.find('.select2-selection__choice'),
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
