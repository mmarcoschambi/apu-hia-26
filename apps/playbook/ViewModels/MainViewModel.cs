using CommunityToolkit.Mvvm.ComponentModel;
using System.Collections.ObjectModel;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace PlaybookDesktop.ViewModels;

public partial class PlaybookChapter : ObservableObject
{
    [ObservableProperty]
    private string _title = string.Empty;

    [ObservableProperty]
    private string _content = string.Empty;
}

public class PlaybookVolume
{
    public string Title { get; set; } = string.Empty;
    public ObservableCollection<PlaybookChapter> Chapters { get; set; } = new();
}

public partial class MainViewModel : ViewModelBase
{
    [ObservableProperty]
    private ObservableCollection<PlaybookVolume> _volumes = new();

    [ObservableProperty]
    private PlaybookChapter? _selectedChapter;

    [ObservableProperty]
    private bool _isPaneOpen = true;

    public MainViewModel()
    {
        LoadChapters();
    }

    private string GetVolumeName(int chapterNumber)
    {
        return chapterNumber switch
        {
            <= 4 => "I. FUNDAMENTOS Y ARQUITECTURA",
            <= 9 => "II. AGENT TEAMS & WORKFLOW (SDD)",
            <= 13 => "III. INVESTIGACIÓN Y ALFA (R&D)",
            <= 16 => "IV. EL MOTOR DE BACKTESTING (Simulador)",
            <= 21 => "V. CATÁLOGO DE ESTRATEGIAS Y PORTAFOLIO",
            <= 27 => "VI. PRODUCCIÓN Y VPS (Live Execution)",
            <= 33 => "VII. OPERACIONES Y GOBIERNO",
            _ => "VIII. APÉNDICES"
        };
    }

    private void LoadChapters()
    {
        string docsPath = Path.Combine(System.AppDomain.CurrentDomain.BaseDirectory, "Assets", "Docs");
        string repoRoot = Path.GetFullPath(Path.Combine(System.AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", ".."));
        string memoryPath = Path.Combine(repoRoot, ".cache", "local_memory.json");
        
        var tempChapters = new List<PlaybookChapter>();

        if (Directory.Exists(docsPath))
        {
            var files = Directory.GetFiles(docsPath, "*.md").OrderBy(f => f).ToList();
            foreach (var file in files)
            {
                string fileName = Path.GetFileNameWithoutExtension(file);
                string title = fileName.Replace("_", " ");
                string content = File.ReadAllText(file);
                
                // Inject ScrumBan Memory Board dynamically into Chapter 09
                if (file.Contains("09_Salvaguardas_y_Cierre"))
                {
                    if (File.Exists(memoryPath))
                    {
                        content += "\n\n## 9.3. Historial Operativo (ScrumBan Memory Board)\n\n";
                        content += "> Registro inmutable de eventos, descubrimientos y refactores operativos del sistema.\n\n";
                        
                        try 
                        {
                            var jsonString = File.ReadAllText(memoryPath);
                            using var doc = System.Text.Json.JsonDocument.Parse(jsonString);
                            var entries = doc.RootElement.EnumerateArray().Reverse().ToList();
                            
                            foreach(var entry in entries)
                            {
                                string date = entry.GetProperty("timestamp").GetString()?[..10] ?? "";
                                string eventTitle = entry.GetProperty("title").GetString() ?? "";
                                string type = entry.GetProperty("type").GetString() ?? "";
                                string text = entry.GetProperty("content").GetString() ?? "";
                                
                                string typeIcon = type switch {
                                    "bugfix" => "🐛",
                                    "discovery" => "🔬",
                                    "architecture" => "🏛️",
                                    "pattern" => "🧩",
                                    "config" => "⚙️",
                                    _ => "📝"
                                };

                                content += $"### {typeIcon} [{date}] {eventTitle}\n";
                                content += $"**Tipo:** `{type.ToUpper()}`\n\n";
                                content += $"{text}\n\n---\n\n";
                            }
                        }
                        catch (System.Exception ex)
                        {
                            content += $"\n> ❌ **ERROR**: No se pudo procesar el archivo de memoria. {ex.Message}";
                        }
                    }
                    else
                    {
                        content += "\n\n## 9.3. Historial Operativo (ScrumBan Memory Board)\n\n";
                        content += "> ⚠️ **ADVERTENCIA**: No se encontró el archivo `local_memory.json` en el directorio `.cache`.";
                    }
                }
                
                int chapNumber = 99;
                if (fileName.Length >= 2 && int.TryParse(fileName[..2], out int parsedNum))
                {
                    chapNumber = parsedNum;
                }

                tempChapters.Add(new PlaybookChapter 
                { 
                    Title = title, 
                    Content = content 
                });
            }
        }

        // Group by Volume
        var grouped = tempChapters.GroupBy(c => {
            int num = 99;
            if (c.Title.Length >= 2 && int.TryParse(c.Title[..2], out int p)) num = p;
            return GetVolumeName(num);
        });

        foreach (var group in grouped)
        {
            var vol = new PlaybookVolume { Title = group.Key };
            foreach (var ch in group)
            {
                vol.Chapters.Add(ch);
            }
            Volumes.Add(vol);
        }
        
        SelectedChapter = Volumes.FirstOrDefault()?.Chapters.FirstOrDefault();
    }
}
