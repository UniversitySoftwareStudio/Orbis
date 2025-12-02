namespace Common.DTOs
{
    public class ResponseDto<T>
    {
        public string Message { get; set; } = string.Empty;
        public bool Success { get; set; }
        public T? Data { get; set; } = default!;
        public DateTime Timestamp { get; } = DateTime.UtcNow;
    }
}