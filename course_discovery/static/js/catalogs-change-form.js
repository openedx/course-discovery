var $ = django.jQuery;


$(function () {
    var $prettifyBtn,
        $previewBtn,
        $previewRow,
        $queryRow = $('.form-row.field-query'),
        $queryField = $('#id_query');

    // Create a wrapping <div> for the button, and add an empty label
    // to align the button witth the text input field.
    $previewRow = $('<div><label></label></div>');
    $queryRow.append($previewRow);

    // Create a prettify button
    $prettifyBtn = $('<button/>', {
        // Translators: "Prettify" means formatting the JSON, fixing alignment issues.
        text: gettext('Prettify'),
        click: function (e) {
            var query = $queryField.val();
            e.preventDefault();

            if (query) {
                query = JSON.stringify(JSON.parse(query), null, 2);
                $queryField.val(query);
            }
        }
    });

    $previewRow.append($prettifyBtn);

    // Create a preview button
    $previewBtn = $('<button/>', {
        text: gettext('Preview'),
        click: function (e) {
            var url,
                query = $queryField.val();
            e.preventDefault();

            if (query) {
                // Remove all whitespace
                query = query.replace(/\s/g, "");

                // URL encode
                query = encodeURIComponent(query);

                url = '/api/v1/courses/?q=' + query;
                window.open(url, 'catalog_preview');
            }
        }
    });

    $previewRow.append($previewBtn);
});
