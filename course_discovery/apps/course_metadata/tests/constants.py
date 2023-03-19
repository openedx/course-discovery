"""
Constants defined for use in unit tests.
"""

MOCK_PRODUCTS_DATA = [
    {
        "id": "12345678",
        "name": "CSV Course",
        "altName": "Alternative CSV Course",
        "abbreviation": "TC",
        "altAbbreviation": "UCT",
        "blurb": "A short description for CSV course",
        "language": "Español",
        "subjectMatter": "Marketing",
        "altSubjectMatter": "Design and Marketing",
        "altSubjectMatter1": "Marketing, Sales, and Techniques",
        "universityAbbreviation": "edX",
        "altUniversityAbbreviation": "altEdx",
        "cardUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS9pbWFnZS5qcGc=",
        "edxRedirectUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS8=",
        "edxPlpUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS8=",
        "durationWeeks": 10,
        "effort": "7–10 hours per week",
        'introduction': 'Very short description\n',
        'isThisCourseForYou': 'This is supposed to be a long description',
        'whatWillSetYouApart': "New ways to learn",
        "videoURL": "",
        "lcfURL": "d3d3LmV4YW1wbGUuY29tL2xlYWQtY2FwdHVyZT9pZD0xMjM=",
        "logoUrl": "aHR0cHM6Ly9leGFtcGxlLmNvbS9pbWFnZS5qcGc=g",
        "metaTitle": "SEO Title",
        "metaDescription": "SEO Description",
        "metaKeywords": "Keyword 1, Keyword 2",
        "slug": "csv-course-slug",
        "productType": "short_course",
        "variant": {
                "id": "00000000-0000-0000-0000-000000000000",
                "endDate": "2022-05-06",
                "finalPrice": "1998",
                "startDate": "2022-03-06",
                "regCloseDate": "2022-02-06",
        },
        "curriculum": {
            "heading": "Course curriculum",
            "blurb": "Test Curriculum",
            "modules": [
                {
                    "module_number": 0,
                    "heading": "Module 0",
                    "description": "Welcome to your course"
                },
                {
                    "module_number": 1,
                    "heading": "Module 1",
                    "description": "Welcome to Module 1"
                },
            ]
        },
        "testimonials": [
            {
                "name": "Lorem Ipsum",
                "title": "Gibberish",
                "text": " This is a good course"
            },
        ],
        "faqs": [
            {
                "id": "faq-1",
                "headline": "FAQ 1",
                "blurb": "This should answer it"
            }
        ],
        "certificate": {
            "headline": "About the certificate",
            "blurb": "how this makes you special"
        },
        "stats": {
            "stat1": "90%",
            "stat1Blurb": "<p>A vast number of special beings take this course</p>",
            "stat2": "100 million",
            "stat2Blurb": "<p>VC fund</p>"
        }
    },
]
