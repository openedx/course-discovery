
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



/*
enable mock data by adding global variable:
mock_data=true # true 代表启用
*/
