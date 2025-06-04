// src/utils/userUtils.ts
export const getFullName = (user: { first_name?: string; last_name?: string }): string => {
    const firstName = (user.first_name || '').trim();
    const lastName = (user.last_name || '').trim();
    if (firstName && lastName) return `${firstName} ${lastName}`;
    if (firstName) return firstName;
    if (lastName) return lastName;
    return 'John Doe';
  };