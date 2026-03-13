"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ThumbsUp, ThumbsDown, X } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";

type FeedbackButtonProps = {
  artifactType: "ai_query_session" | "dashboard_report" | "data_prep" | "alert" | "insight";
  artifactId: string;
};

export function FeedbackButton({ artifactType, artifactId }: FeedbackButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [decision, setDecision] = useState<"thumbs_up" | "thumbs_down">("thumbs_up");
  const [comment, setComment] = useState("");

  const feedbackMutation = useMutation({
    mutationFn: (payload: { decision: "thumbs_up" | "thumbs_down" | "dismiss"; comment?: string }) =>
      apiRequest("/api/v1/feedback", {
        method: "POST",
        body: JSON.stringify({
          artifact_type: artifactType,
          artifact_id: artifactId,
          decision: payload.decision,
          comment: payload.comment,
        }),
      }),
    onSuccess: () => {
      setIsOpen(false);
    },
  });

  if (feedbackMutation.isSuccess) {
    return <p className="text-xs text-green-600 font-medium tracking-tight">Thanks for your feedback!</p>;
  }

  if (!isOpen) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-500 font-medium">Was this AI output helpful?</span>
        <Button variant="secondary" size="sm" className="h-7 px-2" onClick={() => { setDecision("thumbs_up"); setIsOpen(true); }}>
          <ThumbsUp className="h-3.5 w-3.5 mr-1" />
          Yes
        </Button>
        <Button variant="secondary" size="sm" className="h-7 px-2" onClick={() => { setDecision("thumbs_down"); setIsOpen(true); }}>
          <ThumbsDown className="h-3.5 w-3.5 mr-1" />
          No
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm w-full max-w-sm space-y-3 relative">
      <Button variant="ghost" size="sm" className="absolute top-1 right-1 h-6 w-6 p-0" onClick={() => setIsOpen(false)}>
        <X className="h-4 w-4" />
      </Button>
      <p className="text-sm font-medium">
        {decision === "thumbs_up" ? "What did you like about this?" : "What could be improved?"}
      </p>
      <Textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Optional comment..."
        className="h-20 text-sm"
      />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={() => setIsOpen(false)}>
          Cancel
        </Button>
        <Button
          size="sm"
          disabled={feedbackMutation.isPending}
          onClick={() => feedbackMutation.mutate({ decision, comment })}
        >
          {feedbackMutation.isPending ? "Submitting..." : "Submit"}
        </Button>
      </div>
    </div>
  );
}
