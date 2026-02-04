/**
 * Tests for the API service module.
 */
import { api } from '../../services/api';

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('api instance', () => {
    it('is defined', () => {
      expect(api).toBeDefined();
    });
  });

  describe('subscriptions endpoint group', () => {
    it('has getPlans method', () => {
      expect(typeof api.subscriptions.getPlans).toBe('function');
    });

    it('has getCurrent method', () => {
      expect(typeof api.subscriptions.getCurrent).toBe('function');
    });

    it('has createCheckout method', () => {
      expect(typeof api.subscriptions.createCheckout).toBe('function');
    });

    it('has cancel method', () => {
      expect(typeof api.subscriptions.cancel).toBe('function');
    });

    it('has resume method', () => {
      expect(typeof api.subscriptions.resume).toBe('function');
    });

    it('has getPortalUrl method', () => {
      expect(typeof api.subscriptions.getPortalUrl).toBe('function');
    });
  });

  describe('store endpoint group', () => {
    it('has getCategories method', () => {
      expect(typeof api.store.getCategories).toBe('function');
    });

    it('has getItems method', () => {
      expect(typeof api.store.getItems).toBe('function');
    });

    it('has getItem method', () => {
      expect(typeof api.store.getItem).toBe('function');
    });

    it('has purchase method', () => {
      expect(typeof api.store.purchase).toBe('function');
    });

    it('has getInventory method', () => {
      expect(typeof api.store.getInventory).toBe('function');
    });

    it('has equipItem method', () => {
      expect(typeof api.store.equipItem).toBe('function');
    });

    it('has unequipItem method', () => {
      expect(typeof api.store.unequipItem).toBe('function');
    });
  });

  describe('leagues endpoint group', () => {
    it('has list method', () => {
      expect(typeof api.leagues.list).toBe('function');
    });

    it('has getCurrent method', () => {
      expect(typeof api.leagues.getCurrent).toBe('function');
    });

    it('has getStandings method', () => {
      expect(typeof api.leagues.getStandings).toBe('function');
    });

    it('has getCurrentSeason method', () => {
      expect(typeof api.leagues.getCurrentSeason).toBe('function');
    });

    it('has getMyStanding method', () => {
      expect(typeof api.leagues.getMyStanding).toBe('function');
    });
  });

  describe('visionBoards endpoint group', () => {
    it('has list method', () => {
      expect(typeof api.visionBoards.list).toBe('function');
    });

    it('has generate method', () => {
      expect(typeof api.visionBoards.generate).toBe('function');
    });

    it('has delete method', () => {
      expect(typeof api.visionBoards.delete).toBe('function');
    });
  });

  describe('existing endpoint groups', () => {
    it('has dreams endpoint group', () => {
      expect(api.dreams).toBeDefined();
    });

    it('has conversations endpoint group', () => {
      expect(api.conversations).toBeDefined();
    });

    it('has tasks endpoint group', () => {
      expect(api.tasks).toBeDefined();
    });

    it('has users endpoint group', () => {
      expect(api.users).toBeDefined();
    });

    it('has notifications endpoint group', () => {
      expect(api.notifications).toBeDefined();
    });
  });
});
