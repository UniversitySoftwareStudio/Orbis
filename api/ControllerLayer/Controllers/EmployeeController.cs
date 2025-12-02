using Microsoft.AspNetCore.Mvc;
using BusinessLayer.Services;
using Common.DTOs;

namespace ControllerLayer.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class EmployeeController: Controller
    {
        private readonly IEmployeeService _employeeService;

        public EmployeeController(IEmployeeService employeeService)
        {
            _employeeService = employeeService;
        }
        
        [HttpGet]
        public async Task<ActionResult<ResponseDto<EmployeeMainViewDto>>> GetAll()
        {
            var result = await _employeeService.GetAll();

            return new ObjectResult(new ResponseDto<List<EmployeeMainViewDto>> () {
                Data = result.Data?.Select(x => x.ToEmployeeMainViewDto()).ToList(), // If it's not null, convert List<Employee> to List<EmployeeMainViewDto>
                Message = result.Message,
                Success = result.Success
            } ) { StatusCode = result.StatusCode };
        }
        
        /* example HTTP methods
        [HttpGet("{id}")]
        public async Task<ActionResult<ResponseDto<EmployeeDto>>> GetById(int id)
        
        [HttpGet("{id}/edit")]
        
        [HttpPost]
        
        [HttpPut]
        */
    }
}