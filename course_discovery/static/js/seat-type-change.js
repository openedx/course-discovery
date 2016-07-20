
$(function () {
    var show_verified_fields,
        hide_verified_fields,
        show_professional_fields,
        hide_professional_fields,
        show_credit_fields,
        hide_credit_fields,
        hide_all_fields,
        change_fields;

    show_verified_fields= function () {
        $('.field-price').show();
        $('.field-upgrade_deadline').show();
    };

    hide_verified_fields = function () {
        $('.field-price').hide();
        $('.field-upgrade_deadline').hide();
    };

    show_professional_fields = function () {
        $('.field-price').show();
    };

    hide_professional_fields = function () {
        $('.field-price').hide();
    };

    show_credit_fields = function () {
        show_verified_fields();
        $('.field-credit_provider').show();
        $('.field-credit_hours').show();
    };

    hide_credit_fields = function () {
        hide_verified_fields();
        $('.field-credit_provider').hide();
        $('.field-credit_hours').hide();
    };

    hide_all_fields = function () {
        hide_verified_fields();
        hide_professional_fields();
        hide_credit_fields()
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
        else if (selected_value === 'credit') {
            hide_all_fields();
            show_credit_fields();
        }
        else {
            hide_all_fields();
        }

    };

    change_fields();

    $('.field-type .input-select').change(function () {
       change_fields(this);
    });
});
