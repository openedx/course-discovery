$(document).on('change', '#id_type', function (e) {
    var $seatBlock = $("#SeatPriceBlock"),
        $creditPrice = $("#creditPrice"),
        selectedSeatType = this.value;
    if (selectedSeatType === 'audit' || selectedSeatType === '') {
        $seatBlock.hide();
    } else{
        $seatBlock.show();
        if (selectedSeatType === 'credit') {
            $creditPrice.show();
        } else {
            $creditPrice.hide();
        }
    }
});
