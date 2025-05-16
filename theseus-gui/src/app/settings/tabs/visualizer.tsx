"use client";
import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

interface VisualizerSettings {
  resolution: {
    width: number;
    height: number;
  };
  fps: number;
  colors: {
    primary: string;
    secondary: string;
    background: string;
  };
}

export function VisualizerTab() {
  const [settings, setSettings] = useState<VisualizerSettings>({
    resolution: {
      width: 1920,
      height: 1080,
    },
    fps: 30,
    colors: {
      primary: '#ffffff',
      secondary: '#000000',
      background: '#000000',
    },
  });

  const handleSave = async () => {
    try {
      const response = await fetch('/api/settings/visualizer-settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (!response.ok) {
        throw new Error('Failed to save visualizer settings');
      }

      toast.success("Visualizer settings saved successfully");
    } catch (error) {
      toast.error("Failed to save visualizer settings");
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h3 className="text-lg font-medium">Resolution</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="width">Width</Label>
            <Input
              id="width"
              type="number"
              value={settings.resolution.width}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSettings({
                  ...settings,
                  resolution: {
                    ...settings.resolution,
                    width: parseInt(e.target.value) || 0,
                  },
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="height">Height</Label>
            <Input
              id="height"
              type="number"
              value={settings.resolution.height}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSettings({
                  ...settings,
                  resolution: {
                    ...settings.resolution,
                    height: parseInt(e.target.value) || 0,
                  },
                })
              }
            />
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-medium">FPS</h3>
        <div className="space-y-2">
          <Label htmlFor="fps">Frames per second</Label>
          <Input
            id="fps"
            type="number"
            value={settings.fps}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setSettings({
                ...settings,
                fps: parseInt(e.target.value) || 0,
              })
            }
          />
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-medium">Colors</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="space-y-2">
            <Label htmlFor="primary">Primary</Label>
            <Input
              id="primary"
              type="color"
              value={settings.colors.primary}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSettings({
                  ...settings,
                  colors: {
                    ...settings.colors,
                    primary: e.target.value,
                  },
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="secondary">Secondary</Label>
            <Input
              id="secondary"
              type="color"
              value={settings.colors.secondary}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSettings({
                  ...settings,
                  colors: {
                    ...settings.colors,
                    secondary: e.target.value,
                  },
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="background">Background</Label>
            <Input
              id="background"
              type="color"
              value={settings.colors.background}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                setSettings({
                  ...settings,
                  colors: {
                    ...settings.colors,
                    background: e.target.value,
                  },
                })
              }
            />
          </div>
        </div>
      </div>

      <Button onClick={handleSave}>Save Settings</Button>
    </div>
  );
} 