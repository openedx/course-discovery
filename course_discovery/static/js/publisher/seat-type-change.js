
$(function () {
    var show_verified_fields,
        hide_verified_fields,
        show_professional_fields,
        hide_professional_fields,
        hide_all_fields,
        change_fields;

    show_verified_fields= function () {
        $('#id_price').prop("readonly", false);
    };

    hide_verified_fields = function () {
        $('#id_price').prop("readonly", true).val('0.00');
    };

    show_professional_fields = function () {
        $('#id_price').prop("readonly", false);
    };

    hide_professional_fields = function () {
        $('#id_price').prop("readonly", true).val('0.00');
    };

    hide_all_fields = function () {
        hide_verified_fields();
        hide_professional_fields();
    };

    change_fields = function (select_tag) {
        if (!select_tag) {
            select_tag = '#id_type';
        }
        var selected_value = $(select_tag).find("option:selected").val();
        if (selected_value === 'verified') {
            hide_all_fields();
            show_verified_fields();
        }
        else if (selected_value === 'professional' || selected_value === 'no-id-professional') {
            hide_all_fields();
            show_professional_fields();
        }
        else {
            hide_all_fields();
        }

    };

    $('#id_type').change(function () {
       change_fields(this);
    });
});
