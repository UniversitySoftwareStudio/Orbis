using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using DataAccessLayer.DbContext;

namespace ControllerLayer.Controllers
{
    [Route("api/[controller]")][ApiController] public class BaseController: Controller
    {
        protected DatabaseContext ? _databaseContext;

        public BaseController(DatabaseContext context)
        {
            _databaseContext = context;
        }
        
        public override void OnActionExecuted(ActionExecutedContext context)
        {
            base.OnActionExecuted(context);
            _databaseContext!.CloseAsync();
        }
    }
}