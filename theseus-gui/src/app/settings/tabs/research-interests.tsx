"use client";
import { useState } from 'react';
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export function ResearchInterestsTab() {
  const [interests, setInterests] = useState('');

  const handleSave = async () => {
    try {
      const response = await fetch('/api/settings/research-interests', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ interests }),
      });

      if (!response.ok) {
        throw new Error('Failed to save research interests');
      }

      toast.success("Research interests saved successfully");
    } catch (error) {
      toast.error("Failed to save research interests");
    }
  };

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="Enter your research interests (one per line)"
        value={interests}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInterests(e.target.value)}
        className="min-h-[200px]"
      />
      <Button onClick={handleSave}>Save Interests</Button>
    </div>
  );
} 