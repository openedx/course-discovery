$(document).ready(function() {

    var dmp = new diff_match_patch();

    function compare() {
        var current = $("#current-title").text();
        var historical = $("#history-title").text();
        var d = dmp.diff_main(current, historical);
        $("#difference-title").html(dmp.diff_prettyHtml(d));
    }

    compare();
});
