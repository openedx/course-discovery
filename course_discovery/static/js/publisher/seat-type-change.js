$(document).on('change', '#id_type, #id_mode', function (e) {
    var $seatBlock = $("#seatPriceBlock"),
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
