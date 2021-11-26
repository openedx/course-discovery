
enable mock data by adding global variable:
mock_data=true # true 代表启用

## Menu
[get program](#get_program)

[add role](#add_role)

[delete_role](#delete_role)

[delete_member](#delete_member)


<a name="get_program"></a>
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


<a name="add_role"></a>
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


<a name="delete_role"></a>
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


<a name="delete_member"></a>
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


