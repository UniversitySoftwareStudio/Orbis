using System.Net;

namespace BusinessLayer.Services
{
    public class ServiceResult < T >
    {
        public bool Success { get; init; }
        public int StatusCode { get; init; }
        public string Message { get; init; } = "";
        public T ? Data { get; init; }
    }
}