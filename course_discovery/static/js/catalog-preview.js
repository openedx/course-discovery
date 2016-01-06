var $alertNoResults, $alertQueryInvalid, $query, $table;

function processApiResponse(response) {
    $table.rows.add(response.results).draw();

    if (response.next) {
        getApiResponse(response.next);
    }
    else if (response.previous == null && response.results.length == 0) {
        $alertNoResults.removeClass('hidden');
    }
}

function getApiResponse(url) {
    $.get(url)
        .done(processApiResponse)
        .fail(function () {
            $alertQueryInvalid.removeClass('hidden');
        });
}

/**
 * Form submission handler. Sends the query to the server and displays the list of courses.\
 */
function onSubmit(e) {
    var query = {
            "query": {
                "query_string": {
                    "query": $query.val(),
                    "analyze_wildcard": true
                }
            }
        },
        url = '/api/v1/courses/?q=' + encodeURIComponent(JSON.stringify(query));

    e.preventDefault();

    $table.clear();
    $alertNoResults.addClass('hidden');
    $alertQueryInvalid.addClass('hidden');

    getApiResponse(url);
}

/**
 * Click handler. Populates the query input with the content of the
 * clicked example query.
 */
function populateQueryWithExample(e) {
    $query.val($(e.target).text());
    $query.focus();
}

/**
 * Populate the list of Elasticsearch fields
 */
function populateFieldsTable() {
    var data = [
        ['end', 'Course end date'],
        ['enrollment_start', 'Enrollment start date'],
        ['enrollment_end', 'Enrollment end date'],
        ['id', 'Course ID'],
        ['name', 'Course name'],
        ['number', 'Course number (e.g. 6.002x)'],
        ['org', 'Organization (e.g. MITx)'],
        ['start', 'Course start date'],
        ['type', 'Type of course (audit, credit, professional, verified)'],
        ['verification_deadline', 'Final date to submit identity verification'],
    ];
    $("#fields").DataTable({
        info: false,
        paging: false,
        columns: [
            {title: 'Name'},
            {title: 'Description'}
        ],
        oLanguage: {
            sSearch: "Filter: "
        },
        data: data
    });
}

$(document).ready(function () {
    $alertNoResults = $('#alertNoResults');
    $alertQueryInvalid = $('#alertQueryInvalid');
    $query = $('#query');
    $table = $('#courses').DataTable({
        info: true,
        paging: true,
        columns: [
            {
                title: 'Course ID',
                data: 'id'
            },
            {
                title: 'Name',
                data: 'name'
            }
        ],
        oLanguage: {
            sSearch: "Filter: "
        }
    });

    $('#queryForm').submit(onSubmit);

    $('.example').click(populateQueryWithExample);

    populateFieldsTable();
});
