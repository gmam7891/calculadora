import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InstagramTab } from "@/components/tabs/InstagramTab";
import { TwitchTab } from "@/components/tabs/TwitchTab";
import { IcpTab } from "@/components/tabs/IcpTab";
import { VodTab } from "@/components/tabs/VodTab";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold tracking-tight text-foreground">VALUATION PRO</h1>
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
            Media Buying Tool v2.1
          </span>
        </div>
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">
          Data-Driven ROI
        </span>
      </header>

      {/* Main */}
      <main className="p-6">
        <Tabs defaultValue="instagram" className="space-y-6">
          <TabsList className="bg-secondary/50 border border-border p-1 h-auto gap-1">
            <TabsTrigger value="instagram" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground text-xs font-mono uppercase tracking-wider px-4 py-2">
              [01] Instagram
            </TabsTrigger>
            <TabsTrigger value="twitch" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground text-xs font-mono uppercase tracking-wider px-4 py-2">
              [02] Twitch
            </TabsTrigger>
            <TabsTrigger value="icp" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground text-xs font-mono uppercase tracking-wider px-4 py-2">
              [03] ICP Calc
            </TabsTrigger>
            <TabsTrigger value="vod" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground text-xs font-mono uppercase tracking-wider px-4 py-2">
              [04] VOD Analyzer
            </TabsTrigger>
          </TabsList>

          <TabsContent value="instagram">
            <InstagramTab />
          </TabsContent>
          <TabsContent value="twitch">
            <TwitchTab />
          </TabsContent>
          <TabsContent value="icp">
            <IcpTab />
          </TabsContent>
          <TabsContent value="vod">
            <VodTab />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
