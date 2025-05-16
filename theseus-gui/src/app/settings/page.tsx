import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResearchInterestsTab } from "./tabs/research-interests";
import { ModelsTab } from "./tabs/models";
import { EmailTab } from "./tabs/email";
import { VisualizerTab } from "./tabs/visualizer";
import { OrchestrationTab } from "./tabs/orchestration";

export default function SettingsPage() {
  return (
    <div className="container mx-auto py-6">
      <h1 className="text-3xl font-bold mb-6">Settings</h1>
      
      <Tabs defaultValue="research-interests" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="research-interests">Research Interests</TabsTrigger>
          <TabsTrigger value="models">Models</TabsTrigger>
          <TabsTrigger value="orchestration">Orchestration</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="visualizer">Visualizer</TabsTrigger>
        </TabsList>

        <TabsContent value="research-interests">
          <Card>
            <CardHeader>
              <CardTitle>Research Interests</CardTitle>
            </CardHeader>
            <CardContent>
              <ResearchInterestsTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="models">
          <Card>
            <CardHeader>
              <CardTitle>Model Configurations</CardTitle>
            </CardHeader>
            <CardContent>
              <ModelsTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="orchestration">
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <OrchestrationTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="email">
          <Card>
            <CardHeader>
              <CardTitle>Email Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <EmailTab />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="visualizer">
          <Card>
            <CardHeader>
              <CardTitle>Visualizer Settings</CardTitle>
            </CardHeader>
            <CardContent>
              <VisualizerTab />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
} 