

## Get Programs that the user has enroll in
- /api/team/v0/?/[program_uuid]/?page=
- /api/program_enrollments/v1/users/edx/programs/?status=enrolled&page=1&page_size=5
- GET
- involve Pagination
### Input:
    {
        ...pagination input
    }
### Output:
    {
        results:[
            uuid:'', // program uuid
            title:'', // program name
            enrollment_start:'', // enrollment date
            end:'' // completion date
        ]
    }


## Get Programs that the user could enroll in
- /api/program_enrollments/v1/users/edx/programs/?title=xxx&status=enrolled&exclude_status_flag=1
- GET
- involve Pagination
### Input:
    {
        ...pagination input
    }
### Output:
    {
        results:[
            uuid:'', // program uuid
            title:'', // program name
        ]
    }


##  enroll in or unenroll a Program 
- /api/program_enrollments/v1/users/edx/programs/
- POST
- involve Common
### Input:
    {
        status:'enrolled',  //The enrollment status (enrolled/canceled/pending)
        cascade_courses:true, // if impact courses
        uuid:'' // program uuid
    }
### Output:
    {
        ...involve Common
    }

