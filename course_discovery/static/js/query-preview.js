require('bootstrap-sass');
require('datatables.net-bs')();

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
    var url = '/api/v1/course_runs/?limit=100&q=' + encodeURIComponent($query.val());

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
        ['announcement', 'Date the course is announced to the public'],
        ['end', 'Course run end date'],
        ['enrollment_start', 'Enrollment start date'],
        ['enrollment_end', 'Enrollment end date'],
        ['key', 'Course run key'],
        ['language', 'Language in which the course is administered'],
        ['max_effort', 'Estimated maximum number of hours necessary to complete the course run'],
        ['min_effort', 'Estimated minimum number of hours necessary to complete the course run'],
        ['number', 'Course number (e.g. 6.002x)'],
        ['org', 'Organization (e.g. MITx)'],
        ['pacing_type', 'Course run pacing. Options are either "instructor_paced" or "self_paced"'],
        ['start', 'Course run start date'],
        ['title', 'Course run title']
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
        autoWidth: true,
        columns: [
            {
                title: 'Course Run Key',
                data: 'key',
                fnCreatedCell: function (nTd, sData, oData, iRow, iCol) {
                    $(nTd).html("<a href='/api/v1/course_runs/" + oData.key + "/' target='_blank'>" + oData.key + "</a>");
                }
            },
            {
                title: 'Title',
                data: 'title'
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
