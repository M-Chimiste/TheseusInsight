"use client";
import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

export function EmailTab() {
  const [recipients, setRecipients] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState('');

  const handleAddEmail = () => {
    if (newEmail && !recipients.includes(newEmail)) {
      setRecipients([...recipients, newEmail]);
      setNewEmail('');
    }
  };

  const handleRemoveEmail = (email: string) => {
    setRecipients(recipients.filter(e => e !== email));
  };

  const handleSave = async () => {
    try {
      const response = await fetch('/api/settings/email-recipients', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ recipients }),
      });

      if (!response.ok) {
        throw new Error('Failed to save email recipients');
      }

      toast.success("Email recipients saved successfully");
    } catch (error) {
      toast.error("Failed to save email recipients");
    }
  };

  const handleTestEmail = async () => {
    try {
      const response = await fetch('/api/settings/send-test-email', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to send test email');
      }

      toast.success("Test email sent successfully");
    } catch (error) {
      toast.error("Failed to send test email");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          type="email"
          placeholder="Enter email address"
          value={newEmail}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewEmail(e.target.value)}
        />
        <Button onClick={handleAddEmail}>Add</Button>
      </div>

      <div className="space-y-2">
        {recipients.map((email) => (
          <div key={email} className="flex items-center justify-between p-2 bg-secondary rounded-md">
            <span>{email}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleRemoveEmail(email)}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave}>Save Recipients</Button>
        <Button variant="outline" onClick={handleTestEmail}>
          Send Test Email
        </Button>
      </div>
    </div>
  );
} 