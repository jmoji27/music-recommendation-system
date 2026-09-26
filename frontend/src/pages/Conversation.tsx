import { useParams } from "react-router-dom";
import { ConversationView } from "../components/ConversationView";

export function Conversation() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const id = Number(conversationId);
  if (!Number.isInteger(id)) return <p className="error">Conversation not found.</p>;
  // key: switching between conversations must reset all the thread state.
  return (
    <div className="conversation-page">
      <ConversationView key={id} conversationId={id} />
    </div>
  );
}
