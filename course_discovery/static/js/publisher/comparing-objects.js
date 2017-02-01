$(document).on('click', '.btn-show-changes', function (e) {

    if ($(this).text() === 'Show changes') {
        $('.field-container').each(function () {
            showDiff($(this).find('span.object'), $(this).find('span.history-object'), $(this).find('span.show-diff'));
        });
        $(this).text('Hide changes');
    } else {
        $('.object').show();
        $('.show-diff').hide();
        $(this).text('Show changes');
    }
});

var dmp =new diff_match_patch();
    function showDiff($object, $historyObject, $outputDiv) {
      var d = dmp.diff_main($object.text(), $historyObject.text());
      $outputDiv.html(dmp.diff_prettyHtml(d));
        $object.hide();
    }


