var $ = django.jQuery;


$(function () {
    var $previewBtn,
        $previewRow,
        $queryRow = $('.form-row.field-query'),
        $queryField = $('#id_query');

    // Create a wrapping <div> for the button, and add an empty label
    // to align the button witth the text input field.
    $previewRow = $('<div><label></label></div>');
    $queryRow.append($previewRow);

    // Create a preview button
    $previewBtn = $('<button/>', {
        text: gettext('Preview'),
        click: function (e) {
            var url,
                query = $queryField.val();
            e.preventDefault();

            if (query) {
                // URL encode
                query = encodeURIComponent(query);

                url = '/api/v1/courses/?q=' + query;
                window.open(url, 'catalog_preview');
            }
        }
    });

    $previewRow.append($previewBtn);
});
