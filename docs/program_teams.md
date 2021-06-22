
enable mock data by adding global variable:
mock_data=true # true 代表启用

## Menu
[get program](#get_program)

<a href="#get_program">get program2</a> 

[add role](#add_role)

## Common
### Input:
    {
        *field_name:'', // * means required; example of value:"useranme@domain.com"
    }
### Output:
    {
        //status: 1, // 1 success; 0 error
        //status: 1, // no need, it can take from http code
        error_message:'successful added'ß
    }


## Pagination
### Input:
    {
        page_no:1, 
        page_size:10, 
    }
### Output:
    {
        count:5 // total record
    }


<a name="get_program">1</a>
## Get Program Team(with members) by Learning Path ID
- /api/team/v0/programadmins/[program_uuid]/
- GET
### Output:
    {
        results:[
          role: "instructor"  triboo_instructor|instructor｜staff,
          user:{
            id:2, 
            email:'',
            username:''
          },
          role:'', // 
          team_id:'xxxx' //deprecated
          
        ]
    }

<a name="add_role">2</a>
## Add Team Member / Add Role
### Url:
- /api/team/v0/programadmins/[program_uuid]/roles/
- POST
### Input:
    {
        *role_name:'', // target role name, staff|instructor
        *email:'', // useranme@domain.com
    }
### Output:
    {
        error_message:'successful added'
    }

## Delete Role
- /api/team/v0/programadmins/[program_uuid]/roles/
- DELETE
### Intput:
    {
        *role_name:'', // target role name, staff
        *email:'', // useranme@domain.com
    }
### Output:
    {
        error_message:'successful added|user not exists'
    }
    
## Delete Member
- /api/team/v0/programadmins/[program_uuid]/
- DELETE
### Intput:
    {
        *email:'', // member's email, useranme@domain.com
    }
### Output:
    {
        error_message:'successful added|user not exists'
    }


