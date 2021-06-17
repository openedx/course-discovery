
enable mock data by adding global variable:
mock_data=true # true 代表启用

## Common

### Input:
    {
        *field_name:'', // * means required; example of value:"useranme@domain.com"
    }
  
###Output:
      {
        //status: 1, // no need, it can take from http code
        error_message:'successful added'ß
      }

## Get Program Team by Learning Path ID
- /api/proxy/discovery/api/v1/programsteams/?program_uuid=xxxxx

### Input:
### Output:
    {
        results:{
          team_id:'xxxx'
          "role": "instructor"  triboo_instructor|instructor｜staff,
          user:[
            id:2, email:'',
            username:''
    
          ]
        }
    }


## New Team Member
###Url:
/api/proxy/discovery/api/v1/programsteams/[program_team-uuid]/users/
  Method: POST
### Input:
    {
        *email:'', // required example:"useranme@domain.com"
    }
  
###Output:
      {
        //status: 1, // 1 success; 0 error
        error_message:'successful added'ß
      }

## Learning Path Team (Members)
- /api/proxy/discovery/api/v1/programsteams/[program_team-uuid]/users/
- GET
### Input:
### Output:
    {
        // error_message:'successful added'
        result:[
            {
              user_name:'',
              email:'',
              role_name:'',  // staff|instructor
            }
        ]
    }

## Delete Team Member
- /api/team/v0/programteams/program_team-eebf10f43b4c4a8f8c0b94f178ef397b/users/?email=edx@example.com
- DELETE
### parameter
    {
        email:''
    }
Output:


## Learning Path Team (Members)  Add | Remove Admin Access
- /api/proxy/discovery/api/v1/programsteams/[program_team-uuid]/users/[user_id]/roles/
- POST | DELETE
### Intput:
    {
        role_name:''  //staff|instructor
    }
### Output:
    {
        error_message:'successful added|user not exists'
    }
