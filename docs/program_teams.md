
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
        *role_name:'', // staff|instructor
        *email:'', // useranme@domain.com
    }
### Output:
    {
        error_message:'successful added'
    }

## Delete Member
- /api/proxy/discovery/api/v1/programsteams/[program_team-uuid]/users/[user_id]/roles/
- DELETE
### Intput:
    {
        *email:'', // useranme@domain.com
    }
### Output:
    {
        error_message:'successful added|user not exists'
    }


