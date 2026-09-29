import { createContext, useContext } from 'react';

export const ThemeModeContext = createContext({ toggle: () => {} });
export const useThemeMode = () => useContext(ThemeModeContext);
