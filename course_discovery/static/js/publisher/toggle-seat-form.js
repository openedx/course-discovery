$(document).ready(function() {
    var $courseRunForm = $('.js-courserun-form'),
        $seatForm = $('.js-seat-form'),
        $courseSelect = $('#id_course');

    // If the rendered SeatForm is hidden, remove it from the DOM.
    if ($seatForm.hasClass('hidden')) {
        $seatForm.detach();
        $seatForm.removeClass('hidden');
    }

    if ($courseSelect.length) {
        // See https://select2.org/programmatic-control/events for information about the select2:select event.
        $courseSelect.on('select2:select', function(e) {
            var usesEntitlements = e.params.data.uses_entitlements;

            $seatForm.detach();
            if (!usesEntitlements) {
                // Remove any errors that may have been initially loaded with the form.
                $seatForm.find('.js-seat-form-errors').remove();

                // Reset inputs before re-attaching the form.
                $seatForm.find('#id_type').val('');
                $seatForm.find('#seatPriceBlock').hide();
                $seatForm.find('#id_price').val('0.0');
                $seatForm.find('#creditPrice').hide();
                $seatForm.find('#id_credit_price').val('0.0');

                // Re-attach the form
                $seatForm.insertAfter($courseRunForm);
            }
        });
    }
});
