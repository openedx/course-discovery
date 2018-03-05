$(document).on('change', '#id_mode', function (e) {
    var $modeBlock = $("#modePriceBlock"),
        selectedMode = this.value;
    if (selectedMode === 'verified' || selectedMode === 'professional') {
        $modeBlock.show();
    } else{
        $modeBlock.hide();
    }
});
