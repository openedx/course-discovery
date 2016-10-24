
function addDatePicker() {
    _.each($('.add-pikaday'), function(el) {
        if (el.getAttribute('datepicker-initialized') !== 'true') {
            new Pikaday({
                field: el,
                format: 'YYYY-MM-DD',
                defaultDate: $(el).val(),
                setDefaultDate: true,
                showTime: false,
                use24hour: false,
                autoClose: true
            });
            el.setAttribute('datepicker-initialized', 'true');
        }
    });
}
