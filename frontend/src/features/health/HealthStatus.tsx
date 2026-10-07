import { useEffect, useState } from "react";

import { getHealth } from "../../api/client";

type Status = "checking" | "online" | "offline";

export function HealthStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    getHealth()
      .then(() => setStatus("online"))
      .catch(() => setStatus("offline"));
  }, []);

  return (
    <p className={`status status--${status}`} role="status">
      API: {status}
    </p>
  );
}
