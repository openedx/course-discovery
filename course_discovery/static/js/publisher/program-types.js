$(document).ready(function () {
    var microMaster = $('#id_is_micromasters'),
        xseries = $('#id_is_xseries');

    if (microMaster.is(':checked')) {
        toggleMicroMaster(true);
    }
    if (xseries.is(':checked')) {
        toggleXseries(true);
    }
    microMaster.click(function () {
        toggleMicroMaster(this.checked);
    });
    xseries.click(function (e) {
        toggleXseries(this.checked)
    });
});

function toggleMicroMaster (checked) {
    // If is-micromaster checkbox value true from db then show the x-micromaster block.
    $('#micromasters_name_group').toggle(checked);
}

function toggleXseries(checked) {
    // If is-xseries checkbox value true from db then show the x-series block.
    $('#xseries_name_group').toggle(checked);
}
