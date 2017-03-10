$(document).on('change', '#id_type', function (e) {
    var $seatBlock = $("#SeatPriceBlock"),
        selectedSeatType = this.value;
    if (selectedSeatType === 'audit' || selectedSeatType === '') {
        $seatBlock.hide();
    } else{
        $seatBlock.show();
    }
});
