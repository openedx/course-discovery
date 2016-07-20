
function addDatePicker() {
    _.each($('.add-pikaday'), function(el) {
        if (el.getAttribute('datepicker-initialized') !== 'true') {
            new Pikaday({
                field: el,
                format: 'YYYY-MM-DD hh:mm:ss',
                defaultDate: $(el).val(),
                setDefaultDate: true,
                showTime: true,
                use24hour: false,
                autoClose: false
            });
            el.setAttribute('datepicker-initialized', 'true');
        }
    });
}
