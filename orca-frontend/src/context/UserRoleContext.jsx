'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

const ROLES = ['fisherman', 'researcher', 'government', 'maritime', 'admin'];
const STORAGE_KEY = 'orca_active_role';

const UserRoleContext = createContext({
  activeRole: 'fisherman',
  setActiveRole: () => {},
  roles: ROLES
});

export function UserRoleProvider({ children }) {
  const [activeRole, setActiveRoleState] = useState('fisherman');

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && ROLES.includes(saved)) setActiveRoleState(saved);
    } catch {}
  }, []);

  const setActiveRole = (role) => {
    if (!ROLES.includes(role)) return;
    setActiveRoleState(role);
    try { localStorage.setItem(STORAGE_KEY, role); } catch {}
  };

  return (
    <UserRoleContext.Provider value={{ activeRole, setActiveRole, roles: ROLES }}>
      {children}
    </UserRoleContext.Provider>
  );
}

export function useUserRole() {
  return useContext(UserRoleContext);
}

export const ROLE_META = {
  fisherman: { label: '🎣 Fisherman', icon: 'Fish', title: 'Fisherman / Vessel Skipper' },
  researcher: { label: '🔬 Researcher', icon: 'Thermometer', title: 'Marine Researcher' },
  government: { label: '🏛️ Government', icon: 'Shield', title: 'Coastal Authority' },
  maritime: { label: '🚢 Maritime', icon: 'Navigation', title: 'Maritime Operations' },
  admin: { label: '⚙️ Admin', icon: 'Settings', title: 'Platform Admin' }
};
